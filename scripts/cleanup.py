#!/usr/bin/env python3
"""Scoped, resumable cleanup for the KSUG.AI Velero lab. No shell interpolation."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


class CommandError(RuntimeError):
    pass


def run(args, missing_ok=False):
    result = subprocess.run(args, text=True, capture_output=True)
    if result.returncode:
        message = result.stderr + result.stdout
        # Never classify authentication, authorization, or connectivity failures as absence.
        absent = ('NOT_FOUND' in message or 'NotFound' in message or
                  'HTTPError 404' in message or 'not found: 404' in message or 'does not exist' in message or
                  'No URLs matched' in message)
        if missing_ok and absent:
            return None
        raise CommandError(f"{' '.join(args)}\n{message.strip()}")
    return result.stdout


class Cleanup:
    def __init__(self, project, cluster, zone, region, bucket, account, repo):
        self.project, self.cluster, self.zone, self.region = project, cluster, zone, region
        self.bucket, self.account, self.repo = bucket, account, repo
        self.email = f'{account}@{project}.iam.gserviceaccount.com'
        self.image_prefix = f'{region}-docker.pkg.dev/{project}/{repo}/'
        self.context = f'gke_{project}_{zone}_{cluster}'
        self.warnings, self.errors = [], []

    def gc(self, *args, missing_ok=False):
        return run(['gcloud', *args, '--project', self.project], missing_ok=missing_ok)

    def data(self, *args, missing_ok=False, projection=None):
        format_arg = '--format=json' + (f'({projection})' if projection else '')
        raw = self.gc(*args, format_arg, missing_ok=missing_ok)
        return json.loads(raw) if raw is not None else None

    def kc(self, *args, missing_ok=False):
        return run(['kubectl', '--context', self.context, '--request-timeout=30s', *args], missing_ok=missing_ok)

    def owned_disk(self, disk):
        labels = disk.get('labels', {})
        return (labels.get('goog-k8s-cluster-name') == self.cluster and
                labels.get('goog-k8s-cluster-location') == self.zone)

    def builds(self):
        builds = self.data('builds', 'list', '--region=global', '--limit=10000',
                           projection='id,images,source.storageSource,logsBucket,status')
        if len(builds) >= 10000:
            raise CommandError('Build history reached the inventory limit; refusing partial artifact cleanup.')
        # The demo build script uses the global Cloud Build endpoint.
        return [b for b in builds if b.get('images') and
                all(image.startswith(self.image_prefix) for image in b['images'])]

    def inventory(self):
        clusters = self.data('container', 'clusters', 'list')
        matching = [c for c in clusters if c['name'] == self.cluster]
        other_zones = [c.get('location', c.get('zone')) for c in matching
                       if c.get('location', c.get('zone')) != self.zone]
        if other_zones:
            raise CommandError(f'Cluster {self.cluster} exists in {other_zones}; set MY_ZONE correctly before cleanup.')
        buckets = self.data('storage', 'buckets', 'list')
        bucket_names = {b.get('name', '').removeprefix('gs://').rstrip('/') for b in buckets}
        repo = self.data('artifacts', 'repositories', 'describe', self.repo,
                         '--location', self.region, missing_ok=True)
        accounts = self.data('iam', 'service-accounts', 'list')
        account = next((a for a in accounts if a.get('email') == self.email), None)
        disks = [d for d in self.data('compute', 'disks', 'list') if self.owned_disk(d)]
        bucket = self.data('storage', 'buckets', 'describe', f'gs://{self.bucket}') if self.bucket in bucket_names else None
        builds = self.builds()
        sources, logs, retained = [], [], []
        for build in builds:
            source = build.get('source', {}).get('storageSource')
            if source:
                # Only object generations explicitly recorded on a matching demo build.
                if not source.get('generation'):
                    raise CommandError(f"Build {build['id']} has no immutable source generation; inspect manually.")
                uri = f"gs://{source['bucket']}/{source['object']}#{source['generation']}"
                if self.data('storage', 'objects', 'describe', uri, missing_ok=True):
                    sources.append(uri)
                else:
                    deleted = self.data('storage', 'objects', 'describe', uri, '--soft-deleted', missing_ok=True)
                    if deleted:
                        retained.append({'uri': uri, 'metadata': {key: value for key, value in deleted.items()
                            if key in {'size', 'soft_delete_time', 'hard_delete_time',
                                       'softDeleteTime', 'hardDeleteTime', 'storage_class'}}})
            log_bucket = build.get('logsBucket', '').removeprefix('gs://').rstrip('/')
            if log_bucket in bucket_names:
                uri = f"gs://{log_bucket}/log-{build['id']}.txt"
                obj = self.data('storage', 'objects', 'describe', uri, missing_ok=True)
                if obj:
                    logs.append(uri + '#' + str(obj['generation']))
        return {'project': self.project, 'cluster_name': self.cluster, 'zone': self.zone,
                'cluster_present': bool(matching), 'disks': disks, 'backup_bucket': bucket,
                'repository_present': repo is not None, 'service_account_present': account is not None,
                'builds': builds, 'source_objects': sorted(set(sources)), 'owned_build_logs': sorted(set(logs)), 'retained_soft_deleted_objects': retained}

    def action(self, description, operation):
        print(description, flush=True)
        try:
            operation()
        except CommandError as exc:
            self.errors.append(str(exc))
            print(f'FAILED: {exc}', file=sys.stderr, flush=True)

    def delete_cluster(self):
        try:
            self.gc('container', 'clusters', 'get-credentials', self.cluster, '--zone', self.zone)
            self.kc('-n', 'velero', 'patch', 'schedule', 'postgres-hourly', '--type=merge',
                    '-p', '{"spec":{"paused":true}}', missing_ok=True)
            self.kc('delete', 'namespace', 'velero-demo', '--ignore-not-found', '--wait=true', '--timeout=180s')
        except CommandError as exc:
            self.warnings.append('Namespace cleanup failed; cluster deletion and labeled-disk cleanup will still run: ' + str(exc))
        self.gc('container', 'clusters', 'delete', self.cluster, '--zone', self.zone, '--quiet')

    def delete_bucket(self):
        # This affects only the dedicated demo backup bucket, never shared build buckets.
        soft = self.gc('storage', 'ls', '--soft-deleted', '--recursive', f'gs://{self.bucket}', missing_ok=True)
        if soft and soft.strip():
            self.warnings.append('Previously soft-deleted backup objects remain subject to their existing retention: ' + soft.strip())
        self.gc('storage', 'buckets', 'update', f'gs://{self.bucket}', '--clear-soft-delete')
        self.gc('storage', 'rm', '--recursive', f'gs://{self.bucket}')

    def apply(self, plan):
        for b in plan['builds']:
            if b.get('status') in {'QUEUED', 'WORKING', 'PENDING'}:
                self.action(f"Cancel demo build {b['id']}", lambda b=b: self.gc('builds', 'cancel', b['id'], '--region=global', '--quiet'))
        if plan['cluster_present']:
            self.action(f'Delete namespace and cluster {self.cluster} in {self.zone}', self.delete_cluster)
        # Namespace deletion normally removes PVC disks. Re-inventory after cluster deletion,
        # and retry only disks bearing this exact cluster's name AND location labels.
        for disk in [d for d in self.data('compute', 'disks', 'list') if self.owned_disk(d)]:
            zone = disk['zone'].split('/')[-1]
            self.action(f"Delete labeled disk {disk['name']} ({zone})",
                        lambda d=disk, z=zone: self.gc('compute', 'disks', 'delete', d['name'], '--zone', z, '--quiet'))
        if plan['backup_bucket']:
            self.action(f'Permanently delete dedicated backup bucket gs://{self.bucket}', self.delete_bucket)
        if plan['repository_present']:
            self.action(f'Delete dedicated image repository {self.repo}',
                        lambda: self.gc('artifacts', 'repositories', 'delete', self.repo, '--location', self.region, '--quiet'))
        for uri in plan['source_objects'] + plan['owned_build_logs']:
            self.action(f'Delete exact build artifact {uri}', lambda uri=uri: self.gc('storage', 'rm', uri, missing_ok=True))
        if plan['service_account_present']:
            self.action(f'Delete dedicated service account {self.email}',
                        lambda: self.gc('iam', 'service-accounts', 'delete', self.email, '--quiet'))
        if plan['source_objects'] or plan['owned_build_logs']:
            self.warnings.append('Shared build buckets are preserved. Their soft-delete/retention policies may retain deleted build artifacts temporarily; this script does not change shared bucket policies.')
        self.warnings.append('Completed Cloud Build history and provider-managed build logs are retained; project-wide logging policies and shared infrastructure are not changed.')

    def verify(self):
        current = self.inventory()
        self.retained = current['retained_soft_deleted_objects']
        if self.retained:
            self.warnings.append('Soft-deleted build source generations remain until Google Cloud retention expires; see retained_soft_deleted_objects in the report.')
        remaining = []
        if current['cluster_present']: remaining.append('GKE cluster')
        remaining.extend('disk: ' + d['name'] for d in current['disks'])
        if current['backup_bucket']: remaining.append('backup bucket')
        if current['repository_present']: remaining.append('image repository')
        if current['service_account_present']: remaining.append('service account')
        remaining.extend(current['source_objects'] + current['owned_build_logs'])
        # GKE manages these resources; report leaks rather than guessing ownership of shared infrastructure.
        for resource in ['instances', 'snapshots', 'addresses', 'forwarding-rules', 'firewall-rules', 'routes']:
            for item in self.data('compute', resource, 'list'):
                if item.get('name', '').startswith('gke-' + self.cluster + '-'):
                    remaining.append(f"{resource}: {item['name']}")
        return remaining


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Delete the resources shown in the preview')
    parser.add_argument('--yes', action='store_true', help='Skip the typed confirmation (requires --apply)')
    parser.add_argument('--report', default='cleanup-report.json', help='Write inventory, results, and warnings as JSON')
    args = parser.parse_args()
    if args.yes and not args.apply:
        parser.error('--yes requires --apply')
    project = os.environ.get('MY_PROJECT_ID', '')
    if not project:
        parser.error('Set MY_PROJECT_ID explicitly')
    cleanup = Cleanup(project, os.environ['MY_CLUSTER'], os.environ['MY_ZONE'], os.environ['MY_REGION'],
                      os.environ['MY_BUCKET'], os.environ['MY_GSA_NAME'], 'velero-demo')
    report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'mode': 'apply' if args.apply else 'preview'}
    exit_code = 0
    try:
        plan = cleanup.inventory()
        report['inventory'] = plan
        summary = {k: v for k, v in plan.items() if k not in {'builds', 'disks', 'backup_bucket', 'retained_soft_deleted_objects'}}
        summary['labeled_disks'] = [d['name'] for d in plan['disks']]
        summary['backup_bucket_present'] = bool(plan['backup_bucket'])
        summary['retained_source_generations'] = len(plan.get('retained_soft_deleted_objects', []))
        print(json.dumps(summary, indent=2), flush=True)
        print('Also checks for leftover GKE VMs, snapshots, IP addresses, forwarding rules, firewall rules, and routes.')
        if args.apply:
            if not args.yes:
                expected = f'{project}/{cleanup.cluster}'
                if input(f'Permanently delete this demo and its backups? Type {expected}: ') != expected:
                    raise CommandError('Confirmation did not match; no resources deleted.')
            cleanup.apply(plan)
            remaining = cleanup.verify()
            report['remaining_resources'] = remaining
            report['retained_soft_deleted_objects'] = cleanup.retained
            report['verified_clean'] = not remaining and not cleanup.errors
            exit_code = 0 if report['verified_clean'] else 1
            print('VERIFIED: no targeted live demo resources remain.' if not remaining else 'REMAINING: ' + ', '.join(remaining))
        else:
            print('PREVIEW ONLY: no resources changed. Run again with --apply to perform cleanup.')
    except (CommandError, ValueError, OSError) as exc:
        cleanup.errors.append(str(exc))
        print(str(exc), file=sys.stderr)
        exit_code = 1
    report.update(warnings=cleanup.warnings, errors=cleanup.errors)
    Path(args.report).write_text(json.dumps(report, indent=2) + '\n')
    for warning in cleanup.warnings:
        print('NOTE: ' + warning, flush=True)
    print('Report:', args.report)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
