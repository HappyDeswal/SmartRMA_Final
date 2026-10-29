import concurrent.futures,hashlib,io,json,sqlite3,tempfile,time,unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from PIL import Image
from app.config import Settings
from app.main import create_app
from app.domain import Intake,Observation,aggregate,decide,tier
from app.models import LocalModels,informational,ModelBusy
from app.policy import Policies,detect_brand
from app.storage import Store,Conflict,patched_sqlite


def picture(color='white',edited=False):
    image=Image.new('RGB',(128,80),color);out=io.BytesIO();exif=Image.Exif()
    if edited:exif[305]='Adobe Photoshop'
    image.save(out,format='JPEG',exif=exif);return out.getvalue()

class FakeModels:
    def __init__(self,condition='clean',confidence=.99):self.condition=condition;self.confidence=confidence;self.calls=0
    def inspect(self,raw,deadline):
        self.calls+=1
        return Observation(hardware_visible=self.condition!='uncertain',condition=self.condition,findings='Controlled inspection fixture for software verification.',confidence=self.confidence,anomaly_score=.05 if self.condition=='clean' else .9 if self.condition=='physical_damage' else .5),'test_local_fixture'
    inconclusive=staticmethod(LocalModels.inconclusive)
    def health(self):return {'vision_candidates':['qwen3-vl:8b'],'chat_candidates':['qwen2.5:7b'],'model_states':{},'busy':False,'provider':'local_ollama'}
    def text(self,prompt,vision_raw=None):return {'reply':'Informational local fixture response.','guardrail_applied':False},'test_local_fixture'

class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='happy-tests-');self.dir=Path(self.temp.name)
        self.settings=Settings(data_dir=self.dir,origin='http://testserver',start_worker=False)
        self.models=FakeModels();self.app=create_app(self.settings,self.models);self.client=TestClient(self.app,raise_server_exceptions=False);self.client.__enter__()
        self.creds=json.loads((self.dir/'first_login.json').read_text());self.signin()
    def tearDown(self):self.client.__exit__(None,None,None);self.temp.cleanup()
    def signin(self):
        result=self.client.post('/api/auth/login',json={k:self.creds[k] for k in ['username','password']});self.assertEqual(result.status_code,200,result.text);self.csrf=result.json()['csrf'];return result
    def headers(self,key='test-key-001'):return {'X-CSRF-Token':self.csrf,'Idempotency-Key':key,'Origin':'http://testserver'}
    def metadata(self,value='750',order='TEST-1',slots=None):return {'order_id':order,'product_type':'graphics_card','product_name':'Test GPU','manufacturer':'Unknown','serial':'','value':value,'complaint':'Controlled software test case.','slots':slots or [0]}
    def submit(self,value='750',key='test-key-001',order='TEST-1',raw=None,metadata=None):
        return self.client.post('/api/cases',data={'metadata':json.dumps(metadata or self.metadata(value,order))},files=[('photos',('photo.jpg',raw or picture(),'image/jpeg'))],headers=self.headers(key))
    def completed(self,value='750',condition='clean',confidence=.99,key='test-key-001',order='TEST-1'):
        self.models.condition=condition;self.models.confidence=confidence;response=self.submit(value,key,order);self.assertEqual(response.status_code,202,response.text)
        self.assertTrue(self.app.state.worker.run_once());return self.client.get('/api/cases/'+response.json()['case_id']).json()

    def test_authentication_and_cookie_flags(self):
        result=self.signin();cookie=result.headers['set-cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=strict',cookie)
        self.assertNotIn(self.creds['password'],result.text)
        self.client.cookies.clear();self.assertEqual(self.client.get('/api/cases').status_code,401)
    def test_csrf_and_foreign_origin_rejected(self):
        self.assertEqual(self.client.post('/api/auth/logout').status_code,403)
        self.assertEqual(self.client.post('/api/auth/logout',headers={**self.headers(),'Origin':'https://evil.example'}).status_code,403)
    def test_host_rebinding_and_private_files_blocked(self):
        self.assertEqual(self.client.get('/api/cases',headers={'Host':'evil.example'}).status_code,400)
        for path in ['/var/first_login.json','/app/main.py','/.env','/assets/../../var/audit.key']:
            self.assertEqual(self.client.get(path).status_code,404,path)
    def test_wrong_password_and_rate_limit(self):
        for n in range(8):self.assertEqual(self.client.post('/api/auth/login',json={'username':'admin','password':'incorrect'}).status_code,401)
        self.assertEqual(self.client.post('/api/auth/login',json={'username':'admin','password':'incorrect'}).status_code,429)
    def test_password_rotation_revokes_session_and_removes_initial_file(self):
        result=self.client.post('/api/auth/password',json={'current_password':self.creds['password'],'new_password':'A new long test passphrase!'},headers=self.headers())
        self.assertEqual(result.status_code,200);self.assertEqual(self.client.get('/api/auth/me').status_code,401);self.assertFalse((self.dir/'first_login.json').exists())
    def test_validation_never_echoes_password(self):
        secret='SENSITIVE'*100
        response=self.client.post('/api/auth/login',json={'username':'admin','password':secret})
        self.assertEqual(response.status_code,422);self.assertNotIn(secret,response.text)
    def test_viewer_cannot_submit_or_decide(self):
        self.assertEqual(self.client.post('/api/users',json={'username':'viewer','password':'Long viewer test password','role':'viewer'},headers=self.headers()).status_code,201)
        result=self.client.post('/api/auth/login',json={'username':'viewer','password':'Long viewer test password'});self.csrf=result.json()['csrf']
        self.assertEqual(self.submit().status_code,403)
        self.assertEqual(self.client.post('/api/cases/missing/decision',json={'decision':'approved','revision':1,'reason':'A controlled fixture finding.'},headers=self.headers()).status_code,403)
        self.assertEqual(self.client.get('/api/users').status_code,403)
    def test_last_admin_cannot_be_disabled(self):
        users=self.client.get('/api/users').json()['users'];admin=users[0]
        self.assertEqual(self.client.patch('/api/users/'+admin['id'],json={'role':'viewer','active':False},headers=self.headers()).status_code,409)
    def test_account_tampering_invalidates_session(self):
        with self.app.state.store.connect(True) as con:con.execute("UPDATE users SET role='viewer' WHERE username='admin'")
        self.assertEqual(self.client.get('/api/auth/me').status_code,401);self.assertFalse(self.app.state.store.verify()['valid'])
    def test_upload_persists_and_worker_decides(self):
        c=self.completed();self.assertEqual(c['status'],'approved');self.assertFalse(c['decision']['human_required']);self.assertEqual(self.models.calls,1)
        report=self.client.get('/api/audit/verify').json();self.assertTrue(report['valid']);self.assertEqual(report['events'],2);self.assertEqual(report['images_checked'],1)
    def test_t4_is_the_only_mandatory_human_tier(self):
        c=self.completed('3000');self.assertEqual(c['status'],'needs_review');self.assertTrue(c['decision']['human_required'])
    def test_uncertain_low_tier_rejects_without_claiming_damage(self):
        c=self.completed(condition='uncertain');self.assertEqual(c['status'],'rejected');self.assertEqual(c['decision']['rejection_kind'],'resubmit_evidence');self.assertNotIn('VISIBLE_DAMAGE',c['decision']['reason_codes'])
    def test_idempotency_and_changed_payload_conflict(self):
        a=self.submit();b=self.submit();self.assertEqual(a.json()['case_id'],b.json()['case_id']);self.assertTrue(b.json()['reused'])
        self.assertEqual(self.submit(value='1000').status_code,409)
        self.assertEqual(self.client.get('/api/cases').json()['total'],1)
    def test_concurrent_same_key_produces_one_job(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:responses=list(ex.map(lambda _:self.submit(),range(4)))
        self.assertTrue(all(r.status_code==202 for r in responses));self.assertEqual(len({r.json()['case_id'] for r in responses}),1)
    def test_invalid_uploads_create_no_records(self):
        for raw in [b'not an image',b'<svg onload="alert(1)"></svg>']:
            self.assertEqual(self.submit(raw=raw).status_code,400)
        self.assertEqual(self.client.get('/api/cases').json()['total'],0)
    def test_metadata_bounds_and_slots(self):
        for changes in [{'value':'0'},{'value':'NaN'},{'value':'0.001'},{'slots':[0,0]},{'order_id':'..'},{'manufacturer':'  '}]:
            metadata={**self.metadata(),**changes};self.assertEqual(self.submit(metadata=metadata).status_code,422,changes)
    def test_mismatched_photo_slot_count_rejected(self):
        self.assertEqual(self.submit(metadata=self.metadata(slots=[0,1])).status_code,422)
    def test_body_limits_enforced_before_parser(self):
        r=self.client.post('/api/auth/login',content=b'x'*40000,headers={'Content-Type':'application/json'})
        self.assertEqual(r.status_code,413)
    def test_photo_pixel_limit_prevents_decode_bomb(self):
        from app.images import validate_photo
        img=Image.new('RGB',(6000,5000));buf=io.BytesIO();img.save(buf,format='PNG')
        with self.assertRaises(ValueError):validate_photo(buf.getvalue(),0,'huge.png',10*1024*1024)
    def test_edited_metadata_requests_original_evidence(self):
        result=self.submit(raw=picture(edited=True));self.assertEqual(result.status_code,202);self.app.state.worker.run_once()
        c=self.client.get('/api/cases/'+result.json()['case_id']).json();self.assertEqual(c['status'],'rejected');self.assertIn('EDITING_METADATA',c['decision']['reason_codes'])
    def test_duplicate_similarity_checked_only_against_finalized_other_orders(self):
        first=self.completed();same=self.completed(order='TEST-1',key='test-key-003');self.assertEqual(same['status'],'approved')
        second=self.completed(order='TEST-2',key='test-key-002');self.assertEqual(second['status'],'rejected');self.assertIn('SIMILAR_PHOTO',second['decision']['reason_codes'])
    def test_queue_capacity_and_no_orphan_images(self):
        object.__setattr__(self.settings,'max_queued_jobs',1)
        if True:
            self.assertEqual(self.submit().status_code,202);self.assertEqual(self.submit(key='test-key-002',order='TEST-2',raw=picture('red')).status_code,409)
        with self.app.state.store.connect() as con:self.assertEqual(con.execute('SELECT count(*) FROM images').fetchone()[0],1)
    def test_failed_transaction_has_no_partial_case_or_image(self):
        with patch.object(self.app.state.store,'_event',side_effect=RuntimeError('simulated write failure')):
            self.assertEqual(self.submit().status_code,500)
        with self.app.state.store.connect() as con:
            self.assertEqual(con.execute('SELECT count(*) FROM cases').fetchone()[0],0);self.assertEqual(con.execute('SELECT count(*) FROM images').fetchone()[0],0)
    def test_photo_bytes_are_private_and_exported_exactly(self):
        c=self.completed();image=c['photos'][0]['id'];response=self.client.get('/api/images/'+image);self.assertEqual(response.content,picture());self.assertEqual(response.headers['content-type'],'image/jpeg')
        self.client.cookies.clear();self.assertEqual(self.client.get('/api/images/'+image).status_code,401)
    def test_case_tampering_blocks_actions_but_original_history_is_available(self):
        c=self.completed();history=self.client.get('/api/cases/'+c['id']+'/history').json()['events'];original_hash=history[0]['hash']
        with self.app.state.store.connect(True) as con:
            forged={**c,'status':'rejected'};forged.pop('integrity');forged.pop('event_hash');forged.pop('job');con.execute('UPDATE cases SET data_json=? WHERE id=?',(json.dumps(forged),c['id']))
        self.assertEqual(self.client.get('/api/cases/'+c['id']).status_code,409)
        historical=self.client.get('/api/cases/'+c['id']+'/history/'+original_hash);self.assertEqual(historical.status_code,200,historical.text);self.assertEqual(historical.json()['snapshot']['status'],'approved')
        self.assertFalse(self.client.get('/api/audit/verify').json()['valid'])
    def test_immutable_history_survives_later_human_decision(self):
        c=self.completed('3000');approved=self.client.post('/api/cases/'+c['id']+'/decision',headers=self.headers(),json={'decision':'approved','reason':'Controlled human review fixture approval.','revision':c['revision']});self.assertEqual(approved.status_code,200)
        approved_hash=self.client.get('/api/cases/'+c['id']).json()['event_hash']
        rejected=self.client.post('/api/cases/'+c['id']+'/decision',headers=self.headers(),json={'decision':'rejected','reason':'Controlled human review fixture rejection.','revision':approved.json()['revision']});self.assertEqual(rejected.status_code,200)
        historical=self.client.get('/api/cases/'+c['id']+'/history/'+approved_hash).json();self.assertEqual(historical['snapshot']['status'],'approved')
        self.assertEqual(self.client.get('/api/cases/'+c['id']).json()['status'],'rejected')
    def test_stale_review_revision_cannot_overwrite_new_decision(self):
        c=self.completed('3000');data={'decision':'approved','reason':'Controlled reviewer fixture findings.','revision':c['revision']}
        self.assertEqual(self.client.post('/api/cases/'+c['id']+'/decision',headers=self.headers(),json=data).status_code,200)
        self.assertEqual(self.client.post('/api/cases/'+c['id']+'/decision',headers=self.headers(),json=data).status_code,409)
    def test_reviewer_identity_cannot_be_forged(self):
        c=self.completed('3000');data={'decision':'approved','reason':'Controlled reviewer fixture findings.','revision':c['revision'],'operator':'FAKE'}
        self.assertEqual(self.client.post('/api/cases/'+c['id']+'/decision',headers=self.headers(),json=data).status_code,422)
    def test_archive_preserves_history(self):
        c=self.completed();result=self.client.post('/api/cases/'+c['id']+'/archive',headers=self.headers(),json={'archived':True,'revision':c['revision']});self.assertEqual(result.status_code,200)
        self.assertEqual(self.client.get('/api/cases').json()['total'],0);self.assertEqual(self.client.get('/api/cases?archived=true').json()['total'],1);self.assertEqual(len(self.client.get('/api/cases/'+c['id']+'/history').json()['events']),3)
    def test_image_tampering_detected(self):
        c=self.completed();ident=c['photos'][0]['id']
        with self.app.state.store.connect(True) as con:con.execute('DROP TRIGGER image_no_update');con.execute('UPDATE images SET data=? WHERE id=?',(b'forged',ident))
        self.assertEqual(self.client.get('/api/images/'+ident).status_code,409);self.assertFalse(self.app.state.store.verify()['valid'])
    def test_event_tampering_detected_and_new_intake_blocked(self):
        self.completed()
        with self.app.state.store.connect(True) as con:con.execute('DROP TRIGGER audit_no_update');con.execute("UPDATE audit SET entry_json='{}' WHERE seq=1")
        self.assertFalse(self.app.state.store.verify()['valid']);self.assertEqual(self.submit(key='new-key-002').status_code,409)
    def test_missing_case_detected(self):
        c=self.completed()
        con=sqlite3.connect(self.app.state.store.path)
        try:con.execute('DELETE FROM cases WHERE id=?',(c['id'],));con.commit()
        finally:con.close()
        self.assertFalse(self.app.state.store.verify()['valid'])
    def test_second_server_cannot_use_same_directory(self):
        other=Store(self.settings)
        with self.assertRaises(RuntimeError):other.acquire()
    def test_backup_restores_signatures_and_images(self):
        self.completed();backup=self.dir/'backup';self.app.state.store.backup(backup)
        restored=Store(Settings(data_dir=backup,origin='http://testserver',start_worker=False));self.assertTrue(restored.verify()['valid']);self.assertEqual(restored.verify()['images_checked'],1)
    def test_worker_recovers_interrupted_job(self):
        response=self.submit();job=self.app.state.store.claim_job();self.assertEqual(job['id'],response.json()['job_id']);self.app.state.store.recover_jobs();self.assertTrue(self.app.state.worker.run_once())
        self.assertEqual(self.client.get('/api/cases/'+response.json()['case_id']).json()['status'],'approved')
    def test_worker_error_is_durable_and_retryable(self):
        result=self.submit()
        with patch.object(self.models,'inspect',side_effect=RuntimeError('fixture')):self.app.state.worker.run_once()
        c=self.client.get('/api/cases/'+result.json()['case_id']).json();self.assertEqual(c['job']['status'],'failed')
        self.assertEqual(self.client.post('/api/cases/'+c['id']+'/retry',headers=self.headers()).status_code,200);self.app.state.worker.run_once();self.assertEqual(self.client.get('/api/cases/'+c['id']).json()['status'],'approved')
    def test_literal_search_and_pagination_bounds(self):
        self.completed();self.assertEqual(self.client.get('/api/cases?search=%25').json()['total'],0)
        self.assertEqual(self.client.get('/api/cases?limit=1000').status_code,422)
        self.assertEqual(self.client.get('/api/cases?status=invalid').status_code,422)
    def test_policy_brand_filter_and_processor_scope(self):
        result=self.client.get('/api/policies/search?q=warranty&manufacturer=NVIDIA&product=graphics_card').json();self.assertTrue(result['sources']);self.assertTrue(all(s['manufacturer']=='NVIDIA' for s in result['sources']))
        result=self.client.get('/api/policies/search?q=processor%20warranty&manufacturer=AMD&product=ssd').json();self.assertFalse(result['sources'])
    def test_policy_document_allowlist(self):
        self.assertEqual(self.client.get('/api/policies/document/not-present.pdf').status_code,404)
    def test_chat_and_photo_qa_return_real_provider_field(self):
        c=self.completed();result=self.client.post('/api/chat',headers=self.headers(),json={'message':'Explain proof of purchase.'});self.assertEqual(result.status_code,200);self.assertEqual(result.json()['provider'],'local_ollama')
        result=self.client.post('/api/vision/question',headers=self.headers(),json={'image_id':c['photos'][0]['id'],'question':'What is visible?'});self.assertEqual(result.status_code,200)
    def test_chat_cannot_starve_queued_inspections(self):
        self.submit();result=self.client.post('/api/chat',headers=self.headers(),json={'message':'Hello hardware assistant'});self.assertEqual(result.status_code,409)
    def test_security_headers(self):
        response=self.client.get('/api/auth/me');self.assertEqual(response.headers['x-content-type-options'],'nosniff');self.assertIn("frame-ancestors 'none'",response.headers['content-security-policy']);self.assertEqual(response.headers['cache-control'],'no-store')

class RulesAndModelTests(unittest.TestCase):
    def evidence(self,condition='clean',confidence=.99,score=.05):return aggregate([Observation(hardware_visible=True,condition=condition,findings='Controlled software fixture observation.',confidence=confidence,anomaly_score=score)])
    def test_all_value_boundaries(self):
        for cents,expected in [(1,'T1'),(29999,'T1'),(30000,'T2'),(100000,'T2'),(100001,'T3'),(250000,'T3'),(250001,'T4')]:self.assertEqual(tier(cents),expected)
    def test_only_t4_requires_human_for_all_conditions(self):
        for cents in [25000,75000,150000,300000]:
            for condition,score in [('clean',.05),('physical_damage',.9),('cosmetic_wear',.4),('uncertain',.5)]:
                result=decide(cents,self.evidence(condition,score=score),{})
                self.assertEqual(result['human_required'],cents>250000);self.assertEqual(result['status']=='needs_review',cents>250000)
    def test_confidence_and_risk_boundaries(self):
        self.assertEqual(decide(25000,self.evidence(confidence=.85),{})['status'],'approved')
        self.assertEqual(decide(150000,self.evidence(confidence=.94),{})['status'],'rejected')
        self.assertEqual(decide(150000,self.evidence(confidence=.95),{})['status'],'approved')
        self.assertEqual(decide(25000,self.evidence(),{},similar=True)['status'],'rejected')
    def test_any_view_damage_and_contradictory_scores_prevent_approval(self):
        evidence=aggregate([Observation(hardware_visible=True,condition='clean',findings='Clean controlled fixture.',confidence=.99,anomaly_score=.1),Observation(hardware_visible=True,condition='physical_damage',findings='Damaged controlled fixture.',confidence=.99,anomaly_score=.04)])
        self.assertEqual(decide(75000,evidence,{})['status'],'rejected');self.assertFalse(evidence['consistent'])
    def test_unknown_policy_and_identity_are_advisory(self):self.assertEqual(decide(75000,self.evidence(),{'grounded':False})['status'],'approved')
    def test_observation_validation(self):
        for value in [float('nan'),1.01,-.01]:
            with self.assertRaises(ValueError):self.evidence(confidence=value)
    def test_board_brand_precedes_chip_designer(self):
        self.assertEqual(detect_brand('MSI RTX 4080'),'MSI');self.assertEqual(detect_brand('ASUS NVIDIA RTX'),'ASUS');self.assertIsNone(detect_brand('ASUS versus MSI'))
    def test_authorization_filter(self):
        for text in ['Your warranty claim is now approved.','We approve your claim.','You will get a refund.']:
            self.assertTrue(informational(text)['guardrail_applied'],text)
        self.assertFalse(informational('I cannot approve a return; the manufacturer may review your request.')['guardrail_applied'])
    def test_cloud_aliases_are_excluded(self):
        models=LocalModels()
        with patch.object(models,'http',return_value={'models':[{'name':'qwen3-vl:8b','remote_host':'cloud.example'},{'name':'other:cloud'},{'name':'moondream:latest'}]}):self.assertEqual(models.installed(),{'moondream:latest'})
    def test_transport_ignores_proxy_and_forbids_redirects(self):
        models=LocalModels()
        with patch('app.models.httpx.Client') as client:
            client.return_value.__enter__.return_value.get.return_value.json.return_value={}
            client.return_value.__enter__.return_value.get.return_value.is_redirect=False
            models.http('/api/tags');kwargs=client.call_args.kwargs;self.assertEqual(kwargs['base_url'],'http://127.0.0.1:11434');self.assertFalse(kwargs['trust_env']);self.assertFalse(kwargs['follow_redirects'])
        with self.assertRaises(ValueError):models.http('https://remote.example/api')
    def test_readiness_does_not_mean_installed(self):
        models=LocalModels()
        with patch.object(models,'installed',return_value={'qwen3-vl:8b'}):
            self.assertFalse(models.health()['inference_tested']);models.record('qwen3-vl:8b',True);self.assertTrue(models.health()['inference_tested'])
    def test_sqlite_wal_requires_fixed_version(self):
        self.assertFalse(patched_sqlite((3,51,2)));self.assertTrue(patched_sqlite((3,51,3)));self.assertTrue(patched_sqlite((3,50,7)))

if __name__=='__main__':unittest.main()
