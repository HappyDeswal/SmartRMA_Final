import json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import test_application as fixtures
from app.models import ModelBusy
from app.indexing import rebuild
ROOT=Path(__file__).resolve().parents[1]

# Reuse the fixture helpers without inheriting/rerunning their tests.
class OperationsTests(unittest.TestCase):
    setUp=fixtures.ApplicationTests.setUp
    tearDown=fixtures.ApplicationTests.tearDown
    signin=fixtures.ApplicationTests.signin
    headers=fixtures.ApplicationTests.headers
    metadata=fixtures.ApplicationTests.metadata
    submit=fixtures.ApplicationTests.submit
    completed=fixtures.ApplicationTests.completed
    def test_busy_model_requeues_without_fake_decision(self):
        result=self.submit().json()
        with patch.object(self.models,'inspect',side_effect=ModelBusy):self.app.state.worker.run_once()
        case=self.client.get('/api/cases/'+result['case_id']).json()
        self.assertEqual(case['job']['status'],'queued');self.assertEqual(case['job']['attempts'],0);self.assertIsNone(case['decision'])
        self.app.state.worker.run_once();self.assertEqual(self.client.get('/api/cases/'+result['case_id']).json()['status'],'approved')
    def test_equivalent_currency_input_is_idempotent(self):
        a=self.submit(value='750').json();b=self.submit(value='750.00').json();self.assertEqual(a['case_id'],b['case_id'])
    def test_server_error_is_private_and_not_cacheable(self):
        with patch.object(self.app.state.store,'submit',side_effect=RuntimeError('sensitive-secret')):r=self.submit()
        self.assertEqual(r.status_code,500);self.assertNotIn('sensitive-secret',r.text);self.assertEqual(r.headers['cache-control'],'no-store')
    def test_admin_recovery_refuses_active_server(self):
        import os
        r=subprocess.run([sys.executable,str(ROOT/'manage.py'),'reset-admin'],env={**os.environ,'HAPPY_DATA_DIR':str(self.dir)},capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertNotIn(self.creds['password'],r.stdout+r.stderr)
    def test_empty_or_bad_policy_rebuild_preserves_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'index.json').write_text('{"catalog":[],"chunks":[]}')
            before=(root/'index.json').read_bytes()
            with self.assertRaises(ValueError):rebuild(root)
            (root/'broken.pdf').write_bytes(b'not a PDF')
            with self.assertRaises(ValueError):rebuild(root)
            self.assertEqual((root/'index.json').read_bytes(),before)
    def test_policy_rebuild_can_read_real_local_pdf(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=next((ROOT/'resources/policies').glob('Warranty - GIGABYTE*.pdf'))
            shutil.copyfile(source,root/source.name);result=rebuild(root)
            self.assertEqual(result['indexed_documents'],1);self.assertGreater(result['total_chunks'],0)
            index=json.loads((root/'index.json').read_text());self.assertEqual(len(index['catalog'][0]['sha256']),64)

    def test_markdown_sources_are_readable_and_never_html(self):
        r=self.client.get('/api/policies/document/nvidia_official_geforce_warranty.md')
        self.assertEqual(r.status_code,200);self.assertIn('text/plain',r.headers['content-type'])
    def test_all_catalog_documents_resolve(self):
        for item in self.client.get('/api/policies').json()['documents']:
            from urllib.parse import quote
            response=self.client.get('/api/policies/document/'+quote(item['filename'],safe=''))
            self.assertEqual(response.status_code,200,item['filename'])

    def test_image_fingerprint_tampering_blocks_new_decisions(self):
        c=self.completed()
        with self.app.state.store.connect(True) as con:
            con.execute('DROP TRIGGER image_no_update')
            con.execute("UPDATE images SET phash='0000000000000000' WHERE id=?",(c['photos'][0]['id'],))
        self.assertFalse(self.app.state.store.verify()['valid'])
        self.assertEqual(self.submit(key='new-key-123').status_code,409)
