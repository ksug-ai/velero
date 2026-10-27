"""Local behavior tests; database calls are mocked. Cloud rehearsal is separate."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ai-app'))
import app as module
import recovery
from retrieval import retrieve


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.patches = [patch.object(module, 'DATA', self.data), patch.object(recovery, 'DATA', self.data)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.conn = MagicMock()
        self.conn.__enter__.return_value = self.conn
        self.db_patch = patch.object(module, 'db', return_value=self.conn)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.client = module.app.test_client()
        logger_patch = patch.object(module.app.logger, 'exception')
        logger_patch.start()
        self.addCleanup(logger_patch.stop)

    def document(self, text='The recovery passphrase is nebula-orchid-42.'):
        raw = text.encode()
        (self.data / ('a' * 32 + '.txt')).write_bytes(raw)
        return {'id': 'a' * 32, 'name': 'recovery.md', 'sha256': hashlib.sha256(raw).hexdigest()}

    def test_upload_stores_bytes_and_parameterized_catalog_record(self):
        response = self.client.post('/api/documents', data={'file': (io.BytesIO(b'Our recovery plan'), '../plan.md')})
        self.assertEqual(response.status_code, 201)
        doc = response.get_json()
        self.assertEqual(doc['name'], 'plan.md')
        self.assertEqual(module.document_path(doc['id']).read_bytes(), b'Our recovery plan')
        args = self.conn.execute.call_args.args
        self.assertIn('VALUES (%s, %s, %s)', args[0])
        self.assertEqual(args[1][2], hashlib.sha256(b'Our recovery plan').hexdigest())

    def test_invalid_uploads_and_questions(self):
        for filename, content in [('bad.pdf', b'hi'), ('bad.txt', b'\xff'), ('empty.txt', b' '), ('binary.md', b'hello\x00')]:
            response = self.client.post('/api/documents', data={'file': (io.BytesIO(content), filename)})
            self.assertEqual(response.status_code, 400)
        for payload in [{}, {'question': []}, {'question': ' '}, {'question': 'x' * 2001}, ['bad']]:
            self.assertEqual(self.client.post('/api/chat', json=payload).status_code, 400)
        self.assertEqual(self.client.post('/api/documents', data={'file': (io.BytesIO(b'x' * 300000), 'big.txt')}).status_code, 413)

    def test_chat_retrieves_uploaded_text_and_saves_history(self):
        self.conn.execute.return_value.fetchall.return_value = [self.document()]
        response = self.client.post('/api/chat', json={'question': 'What is the recovery passphrase?'})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('nebula-orchid-42', data['answer'])
        self.assertEqual(data['mode'], 'extractive')
        args = self.conn.execute.call_args.args
        self.assertIn('INSERT INTO conversations', args[0])
        self.assertEqual(args[1][0], 'What is the recovery passphrase?')

    def test_missing_or_corrupted_document_fails_instead_of_answering(self):
        row = self.document()
        self.conn.execute.return_value.fetchall.return_value = [row]
        path = module.document_path(row['id'])
        path.write_text('different contents')
        self.assertEqual(self.client.get('/api/state').status_code, 503)
        path.unlink()
        self.assertEqual(self.client.get('/api/state').status_code, 503)
        with self.assertRaises(ValueError):
            module.document_path('../../etc/passwd')

    def test_ollama_failure_is_visible_and_does_not_save_fake_answer(self):
        self.conn.execute.return_value.fetchall.return_value = [self.document()]
        with patch.object(module, 'MODE', 'ollama'), patch.object(module.http, 'urlopen', side_effect=URLError('offline')):
            response = self.client.post('/api/chat', json={'question': 'recovery passphrase'})
        self.assertEqual(response.status_code, 502)
        self.assertFalse(any('INSERT INTO conversations' in call.args[0] for call in self.conn.execute.call_args_list))

    def test_checkpoint_detects_history_changes_after_restore(self):
        row = self.document()
        turns = [{'id': 1, 'question': 'passphrase?', 'answer': 'nebula-orchid-42', 'mode': 'extractive', 'sources': []}]
        def execute(query, *args):
            result = MagicMock()
            result.fetchall.return_value = turns if 'FROM conversations' in query else [row]
            return result
        self.conn.execute.side_effect = execute
        with patch.object(recovery, 'db', return_value=self.conn):
            with patch.object(sys, 'argv', ['recovery.py', 'checkpoint']): recovery.main()
            with patch.object(sys, 'argv', ['recovery.py', 'verify']): recovery.main()
            turns[0]['answer'] = 'changed'
            with patch.object(sys, 'argv', ['recovery.py', 'verify']), self.assertRaises(RuntimeError): recovery.main()

    def test_no_matching_document_does_not_invent_an_answer(self):
        self.assertEqual(retrieve('quantum computing', [('plan.txt', 'Daily database backups')]), [])

    def test_ui_loads_and_does_not_interpret_history_as_html(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        with self.client.get('/static/app.js') as response:
            js = response.get_data(as_text=True)
        self.assertIn('textContent', js)
        self.assertNotIn('innerHTML', js)


if __name__ == '__main__':
    unittest.main()
