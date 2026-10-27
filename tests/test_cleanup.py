"""Cleanup safety and resumability tests; no cloud commands run."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch, MagicMock

spec = importlib.util.spec_from_file_location('cleanup', Path(__file__).resolve().parents[1] / 'scripts/cleanup.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.cleaner = module.Cleanup('test-project', 'velero-demo', 'us-central1-c', 'us-central1',
                                      'test-project-velero-demo', 'velero-demo', 'velero-demo')

    def test_empty_project_inventory_handles_deleted_identities(self):
        def data(*args, **kwargs):
            if args[:3] == ('artifacts', 'repositories', 'describe'):
                return None
            return []
        with patch.object(self.cleaner, 'data', side_effect=data):
            inventory = self.cleaner.inventory()
        self.assertFalse(inventory['cluster_present'])
        self.assertFalse(inventory['repository_present'])
        self.assertFalse(inventory['service_account_present'])
        self.assertIsNone(inventory['backup_bucket'])
        self.assertEqual(inventory['source_objects'], [])

    def test_only_disks_with_exact_cluster_and_zone_labels_are_owned(self):
        def disk(name, zone):
            return {'labels': {'goog-k8s-cluster-name': name, 'goog-k8s-cluster-location': zone}}
        self.assertTrue(self.cleaner.owned_disk(disk('velero-demo', 'us-central1-c')))
        self.assertFalse(self.cleaner.owned_disk(disk('velero-demo-old', 'us-central1-c')))
        self.assertFalse(self.cleaner.owned_disk(disk('velero-demo', 'us-central1-f')))
        self.assertFalse(self.cleaner.owned_disk({'name': 'gke-velero-demo-looks-related'}))

    def test_permission_denied_is_never_treated_as_missing(self):
        result = subprocess.CompletedProcess([], 1, '', 'PERMISSION_DENIED: HTTPError 403')
        with patch.object(module.subprocess, 'run', return_value=result), self.assertRaises(module.CommandError):
            module.run(['gcloud', 'read'], missing_ok=True)

    def test_known_absence_allows_reruns(self):
        for message in ['HTTPError 404: NOT_FOUND', 'gs://bucket/object#123 not found: 404.']:
            result = subprocess.CompletedProcess([], 1, '', message)
            with patch.object(module.subprocess, 'run', return_value=result):
                self.assertIsNone(module.run(['gcloud', 'read'], missing_ok=True))

    def test_wrong_zone_stops_inventory(self):
        with patch.object(self.cleaner, 'data', return_value=[{'name': 'velero-demo', 'location': 'us-central1-f'}]), self.assertRaises(module.CommandError):
            self.cleaner.inventory()

    def test_shared_builds_are_not_selected(self):
        prefix = self.cleaner.image_prefix
        builds = [{'id': 'ours', 'images': [prefix + 'ai:one']},
                  {'id': 'shared', 'images': [prefix + 'ai:two', 'unrelated/image']},
                  {'id': 'other', 'images': [prefix.replace('velero-demo/', 'velero-demo-other/') + 'ai:three']}]
        with patch.object(self.cleaner, 'data', return_value=builds):
            self.assertEqual([b['id'] for b in self.cleaner.builds()], ['ours'])

    def test_bucket_soft_delete_disabled_before_recursive_removal(self):
        with patch.object(self.cleaner, 'gc', return_value='') as gc:
            self.cleaner.delete_bucket()
        commands = [call.args for call in gc.call_args_list]
        self.assertEqual(commands[1], ('storage', 'buckets', 'update', 'gs://test-project-velero-demo', '--clear-soft-delete'))
        self.assertEqual(commands[2], ('storage', 'rm', '--recursive', 'gs://test-project-velero-demo'))

    def test_failed_kubernetes_access_does_not_prevent_exact_cluster_deletion(self):
        def gc(*args, **kwargs):
            if 'get-credentials' in args:
                raise module.CommandError('API unavailable')
            return ''
        with patch.object(self.cleaner, 'gc', side_effect=gc) as mock:
            self.cleaner.delete_cluster()
        self.assertIn(('container', 'clusters', 'delete', 'velero-demo', '--zone', 'us-central1-c', '--quiet'),
                      [call.args for call in mock.call_args_list])
        self.assertTrue(self.cleaner.warnings)

    def test_empty_plan_is_resumable_without_deletions(self):
        plan = {'builds': [], 'cluster_present': False, 'backup_bucket': None,
                'repository_present': False, 'service_account_present': False,
                'source_objects': [], 'owned_build_logs': []}
        with patch.object(self.cleaner, 'data', return_value=[]), patch.object(self.cleaner, 'gc') as gc:
            self.cleaner.apply(plan)
            gc.assert_not_called()

    def test_only_exact_recorded_source_generation_is_deleted(self):
        uri = 'gs://shared-build-bucket/source/exact-demo-build.tgz#123'
        plan = {'builds': [], 'cluster_present': False, 'backup_bucket': None,
                'repository_present': False, 'service_account_present': False,
                'source_objects': [uri], 'owned_build_logs': []}
        with patch.object(self.cleaner, 'data', return_value=[]), patch.object(self.cleaner, 'gc') as gc:
            self.cleaner.apply(plan)
            gc.assert_called_once_with('storage', 'rm', uri, missing_ok=True)


class CleanupCliTests(unittest.TestCase):
    def test_preview_never_invokes_apply_and_saves_report(self):
        import json
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            report = str(Path(directory) / 'report.json')
            cleaner = MagicMock()
            cleaner.inventory.return_value = {'builds': [], 'disks': [], 'backup_bucket': None}
            cleaner.warnings, cleaner.errors = [], []
            environment = {'MY_PROJECT_ID': 'test-project', 'MY_CLUSTER': 'velero-demo',
                           'MY_ZONE': 'us-central1-c', 'MY_REGION': 'us-central1',
                           'MY_BUCKET': 'test-project-velero-demo', 'MY_GSA_NAME': 'velero-demo'}
            with patch.dict(os.environ, environment), patch.object(module, 'Cleanup', return_value=cleaner), patch.object(module.sys, 'argv', ['cleanup.py', '--report', report]):
                self.assertEqual(module.main(), 0)
            cleaner.apply.assert_not_called()
            cleaner.verify.assert_not_called()
            self.assertEqual(json.loads(Path(report).read_text())['mode'], 'preview')

    def test_retained_bytes_are_reported_separately_from_live_cleanup(self):
        import json
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            report = str(Path(directory) / 'report.json')
            cleaner = MagicMock()
            cleaner.inventory.return_value = {'builds': [], 'disks': [], 'backup_bucket': None}
            cleaner.verify.return_value = []
            cleaner.retained = [{'uri': 'gs://shared/demo#1', 'metadata': {'hardDeleteTime': 'future'}}]
            cleaner.warnings, cleaner.errors = ['Retention remains'], []
            environment = {'MY_PROJECT_ID': 'test-project', 'MY_CLUSTER': 'velero-demo',
                           'MY_ZONE': 'us-central1-c', 'MY_REGION': 'us-central1',
                           'MY_BUCKET': 'test-project-velero-demo', 'MY_GSA_NAME': 'velero-demo'}
            with patch.dict(os.environ, environment), patch.object(module, 'Cleanup', return_value=cleaner), patch.object(module.sys, 'argv', ['cleanup.py', '--apply', '--yes', '--report', report]):
                self.assertEqual(module.main(), 0)
            result = json.loads(Path(report).read_text())
            self.assertTrue(result['verified_clean'])
            self.assertEqual(len(result['retained_soft_deleted_objects']), 1)
