"""Test real installer execution using local release fixtures, never the network."""
import hashlib
import io
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VeleroInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'scripts').mkdir()
        shutil.copy(ROOT / 'scripts/install-velero-cli.sh', self.root / 'scripts')
        shutil.copy(ROOT / 'setenv.sh', self.root)
        system = platform.system().lower()
        arch = 'arm64' if platform.machine() in {'arm64', 'aarch64'} else 'amd64'
        self.folder = f'velero-v1.18.1-{system}-{arch}'
        archive = self.root / (self.folder + '.tar.gz')
        contents = b'#!/usr/bin/env bash\necho "Version: v1.18.1"\n'
        with tarfile.open(archive, 'w:gz') as tar:
            entry = tarfile.TarInfo(self.folder + '/velero')
            entry.size, entry.mode = len(contents), 0o755
            tar.addfile(entry, io.BytesIO(contents))
        self.checksum = self.root / 'CHECKSUM'
        self.checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
        tools = self.root / 'bin'
        tools.mkdir()
        (tools / 'curl').write_text('''#!/usr/bin/env bash
[[ "${MOCK_CURL_FAIL:-0}" == 0 ]] || exit 1
case "$2" in
 */CHECKSUM) cp "$MOCK_CHECKSUM" "$4" ;;
 *) cp "$MOCK_ARCHIVE" "$4" ;;
esac
''')
        (tools / 'curl').chmod(0o755)
        self.env = {**os.environ, 'PATH': str(tools) + ':' + os.environ['PATH'], 'VELERO_VERSION': 'v1.18.1',
                    'MOCK_ARCHIVE': str(archive), 'MOCK_CHECKSUM': str(self.checksum)}

    def run_installer(self, **extra):
        return subprocess.run(['bash', str(self.root / 'scripts/install-velero-cli.sh')],
                              env={**self.env, **extra}, capture_output=True, text=True)

    def test_verified_archive_installs_without_sudo_or_path_changes(self):
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        cli = Path(result.stdout.strip())
        self.assertTrue(cli.is_file())
        self.assertTrue(os.access(cli, os.X_OK))
        self.assertEqual(subprocess.check_output([str(cli), 'version', '--client-only'], text=True).strip(), 'Version: v1.18.1')

    def test_bad_checksum_prevents_installation(self):
        self.checksum.write_text('0' * 64 + '  ' + self.folder + '.tar.gz\n')
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('checksum verification failed', result.stderr)
        self.assertFalse((self.root / '.tools' / self.folder / 'velero').exists())

    def test_cached_cli_works_when_download_is_unavailable(self):
        first = self.run_installer()
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_installer(MOCK_CURL_FAIL='1')
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
