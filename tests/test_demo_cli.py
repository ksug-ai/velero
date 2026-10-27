"""Exercise shell guards with fake CLIs; never contacts a cluster."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DemoCliTests(unittest.TestCase):
    def run_demo(self, command, **settings):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'kubectl').write_text('''#!/bin/bash
case "$*" in
 'config current-context') echo "${MOCK_CONTEXT:-gke_test-project_us-central1-f_velero-demo}" ;;
 'get namespace velero-demo') exit 0 ;;
 *'get deployment/ai-assistant'*) exit "${MOCK_APP_MISSING:-0}" ;;
 *'exec deployment/ai-assistant -- python recovery.py checkpoint') exit 0 ;;
 *'get backup '*) echo Completed ;;
 *'get podvolumebackups'*'spec.volume'*) printf '%s\n' "${MOCK_VOLUMES:-backup documents}" | tr ' ' '\\n' ;;
 *'get podvolumebackups'*) printf 'Completed\\nCompleted\\n' ;;
 *) echo "Unexpected kubectl: $*" >&2; exit 9 ;;
esac
''')
            (path / 'velero').write_text('#!/bin/bash\nexit 0\n')
            for p in path.iterdir():
                p.chmod(0o755)
            env = {**os.environ, 'PATH': directory + ':' + os.environ['PATH'],
                   'MY_PROJECT_ID': 'test-project', 'MY_CLUSTER': 'velero-demo',
                   'MY_ZONE': 'us-central1-f', **settings}
            return subprocess.run(['bash', str(ROOT / 'demo.sh'), *command], env=env,
                                  capture_output=True, text=True)

    def test_wrong_context_stops_before_backup(self):
        result = self.run_demo(['backup', 'test'], MOCK_CONTEXT='wrong')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Expected kubectl context', result.stderr)

    def test_restore_refuses_existing_namespace(self):
        result = self.run_demo(['restore', 'test'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Delete the demo namespace', result.stderr)

    def test_missing_app_cannot_be_reported_as_success(self):
        self.assertNotEqual(self.run_demo(['backup', 'test'], MOCK_APP_MISSING='1').returncode, 0)

    def test_completed_backup_missing_documents_is_rejected(self):
        result = self.run_demo(['backup', 'test'], MOCK_VOLUMES='backup')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing volume backup: documents', result.stderr)

    def test_both_completed_volume_backups_are_accepted(self):
        result = self.run_demo(['backup', 'test'])
        self.assertEqual(result.returncode, 0, result.stderr)
