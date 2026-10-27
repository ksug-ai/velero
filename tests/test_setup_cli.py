"""Run the actual setup/build/deploy scripts against fake cloud CLIs."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SetupCliTests(unittest.TestCase):
    def run_script(self, script, args=(), **overrides):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'gcloud').write_text('''#!/usr/bin/env bash
printf 'gcloud %s\\n' "$*" >> "$MOCK_LOG"
case "$*" in
 'container clusters list '*) printf '%s\\n' "${MOCK_CLUSTER_INFO-us-central1-f\tRUNNING}" ;;
 'builds submit '*) exit "${MOCK_BUILD_FAILURE:-0}" ;;
esac
''')
            (path / 'kubectl').write_text('''#!/usr/bin/env bash
printf 'kubectl %s\\n' "$*" >> "$MOCK_LOG"
case "$*" in
 'config current-context') echo "${MOCK_CONTEXT:-gke_test-project_us-central1-f_velero-demo}" ;;
 '-n velero-demo get deployment/postgres') exit "${MOCK_POSTGRES_MISSING:-0}" ;;
 '-n velero-demo get service/ai-assistant') exit "${MOCK_SERVICE_MISSING:-0}" ;;
 'apply -f -') cat > "$MOCK_MANIFEST" ;;
 *'exec -i deployment/postgres'*) cat >/dev/null ;;
 *'rollout status deployment/ai-assistant'*) exit "${MOCK_ROLLOUT_FAILURE:-0}" ;;
esac
''')
            (path / 'velero').write_text('''#!/usr/bin/env bash
printf 'velero %s\\n' "$*" >> "$MOCK_LOG"
if [[ "$*" == 'version --client-only' ]]; then echo 'Version: v1.18.1'; fi
''')
            for tool in ['gcloud', 'kubectl', 'velero']:
                (path / tool).chmod(0o755)
            log = path / 'commands.log'
            manifest = path / 'applied.yaml'
            env = {**os.environ, 'PATH': directory + ':' + os.environ['PATH'],
                   'MY_PROJECT_ID': 'test-project', 'MY_CLUSTER': 'velero-demo',
                   'MY_ZONE': 'us-central1-f', 'MY_REGION': 'us-central1',
                   'MY_BUCKET': 'test-project-velero-demo', 'MY_GSA_NAME': 'velero-demo',
                   'VELERO_VERSION': 'v1.18.1', 'GCP_PLUGIN_VERSION': 'v1.14.4',
                   'AI_APP_IMAGE': '', 'MOCK_LOG': str(log), 'MOCK_MANIFEST': str(manifest), **overrides}
            # An unrelated cwd proves that script-relative paths work.
            result = subprocess.run(['bash', str(ROOT / script), *args], cwd=directory,
                                    env=env, capture_output=True, text=True)
            return result, log.read_text() if log.exists() else '', manifest.read_text() if manifest.exists() else ''

    def test_default_build_also_deploys_and_checks_service(self):
        result, log, manifest = self.run_script('ai-app/build-and-push.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('deployment complete', result.stdout)
        self.assertIn('gcloud builds submit', log)
        self.assertIn('kubectl apply -f -', log)
        self.assertIn('kubectl -n velero-demo get service/ai-assistant', log)
        self.assertIn('us-central1-docker.pkg.dev/test-project/velero-demo/ai-assistant:', manifest)
        self.assertNotIn('AI_APP_IMAGE_PLACEHOLDER', manifest)
        self.assertLess(log.index('gcloud builds submit'), log.index('kubectl apply -f -'))

    def test_explicit_build_only_does_not_touch_kubernetes(self):
        result, log, _ = self.run_script('ai-app/build-and-push.sh', ['--build-only'], MOCK_CONTEXT='wrong')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('NOT been deployed', result.stdout)
        self.assertNotIn('kubectl ', log)

    def test_wrong_context_stops_before_billed_build(self):
        result, log, _ = self.run_script('ai-app/build-and-push.sh', MOCK_CONTEXT='wrong')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('gcloud builds submit', log)

    def test_missing_postgres_stops_before_billed_build(self):
        result, log, _ = self.run_script('ai-app/build-and-push.sh', MOCK_POSTGRES_MISSING='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PostgreSQL is missing', result.stderr)
        self.assertNotIn('gcloud builds submit', log)

    def test_build_failure_never_deploys(self):
        result, log, _ = self.run_script('ai-app/build-and-push.sh', MOCK_BUILD_FAILURE='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('kubectl apply -f -', log)
        self.assertNotIn('deployment complete', result.stdout)

    def test_missing_service_never_reports_success(self):
        result, _, _ = self.run_script('ai-app/build-and-push.sh', MOCK_SERVICE_MISSING='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('deployment complete', result.stdout)

    def test_failed_rollout_never_reports_success(self):
        result, _, _ = self.run_script('ai-app/build-and-push.sh', MOCK_ROLLOUT_FAILURE='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('deployment complete', result.stdout)

    def test_setup_reuses_cluster_and_existing_image(self):
        image = 'us-central1-docker.pkg.dev/test-project/velero-demo/ai-assistant:existing'
        result, log, manifest = self.run_script('setup.sh', AI_APP_IMAGE=image)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('demo setup complete', result.stdout)
        self.assertIn('container clusters get-credentials velero-demo', log)
        self.assertNotIn('container clusters create ', log)
        self.assertNotIn('builds submit', log)
        self.assertIn(image, manifest)
        self.assertLess(log.index('deployment/postgres'), log.index('kubectl apply -f -'))
        self.assertLess(log.index('get service/ai-assistant'), log.index('velero install'))

    def test_setup_creates_cluster_and_automatically_deploys_built_image(self):
        result, log, manifest = self.run_script('setup.sh', MOCK_CLUSTER_INFO='')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('container clusters create velero-demo', log)
        self.assertIn('gcloud builds submit', log)
        self.assertIn('kind: Service', manifest)
        self.assertIn('demo setup complete', result.stdout)

    def test_setup_rejects_wrong_cluster_zone(self):
        result, log, _ = self.run_script('setup.sh', MOCK_CLUSTER_INFO='us-central1-c\tRUNNING')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Set MY_ZONE', result.stderr)
        self.assertNotIn('builds submit', log)
        self.assertNotIn('container clusters create ', log)

    def test_setup_waits_for_existing_cluster_to_be_running(self):
        result, log, _ = self.run_script('setup.sh', MOCK_CLUSTER_INFO='us-central1-f\tPROVISIONING')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('builds submit', log)
        self.assertNotIn('demo setup complete', result.stdout)
