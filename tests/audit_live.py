"""Opt-in real local three-node audit. Creates four labelled test orders, never approves T4."""
import hashlib,json,time,uuid
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
run_id='AUDIT-'+time.strftime('%Y%m%d-%H%M%S')
manifest=json.loads((ROOT/'sample_data/manifest.json').read_text())
with httpx.Client(base_url='http://127.0.0.1:8010',trust_env=False,timeout=145) as client:
    me=client.get('/api/auth/me');me.raise_for_status();headers={'X-CSRF-Token':me.json()['csrf']}
    initial=client.get('/api/audit/verify').json();assert initial['valid']
    system=client.get('/api/system').json();assert all(n['reachable'] for n in system['nodes'])
    assert system['models']['vision_candidates'],'Local vision models must be installed and Ollama running.'
    ids=[]
    choices=[('T1','graphics_card','T1/05_graphics_card.jpg',250),('T2','motherboard','T2/05_motherboard.jpg',750),('T3','ram','T3/05_ram.jpg',1500),('T4','ssd','T4/05_ssd.jpg',3000)]
    for tier,product,file,value in choices:
        item=next(r for r in manifest if r['file']==file)
        metadata={'order_id':run_id+'-'+tier,'product_type':product,'product_name':item['product_name']+' · audit test','manufacturer':'Unknown','value':str(value),'complaint':'Labelled software audit with an attributed sample photo and synthetic tier price.','slots':[0]}
        r=client.post('/api/cases',headers={**headers,'Idempotency-Key':uuid.uuid4().hex},data={'metadata':json.dumps(metadata)},files={'photos':('original.jpg',(ROOT/'sample_data'/file).read_bytes(),'image/jpeg')});r.raise_for_status();ids.append(r.json()['case_id'])
    deadline=time.monotonic()+1100
    while True:
        cases=[client.get('/api/cases/'+ident).json() for ident in ids]
        print([(c['tier'],c['status'],c['job']['status']) for c in cases],flush=True)
        if all(c['job']['status'] in {'complete','failed'} for c in cases):break
        assert time.monotonic()<deadline,'Live jobs exceeded the audit wait budget.'
        time.sleep(8)
    assert all(c['job']['status']=='complete' for c in cases)
    assert cases[-1]['status']=='needs_review' and cases[-1]['decision']['human_required']
    assert all(c['status'] in {'approved','rejected'} and not c['decision']['human_required'] for c in cases[:-1])
    for c in cases:
        assert c['observations'] and c['observations'][0]['model'],'A real local model must have returned evidence.'
        exported=client.get('/api/cases/'+c['id']+'/export');exported.raise_for_status()
        import base64
        for image in exported.json()['images']:assert hashlib.sha256(base64.b64decode(image['base64'])).hexdigest()==image['sha256']
    audit=client.get('/api/audit/verify').json();assert audit['valid']
    chat=client.post('/api/chat',headers=headers,json={'message':'Briefly explain why a hardware photo cannot prove electrical function.'});chat.raise_for_status()
    qa=client.post('/api/vision/question',headers=headers,json={'image_id':cases[0]['photos'][0]['id'],'question':'In one sentence describe the visible PC component. Do not infer electrical function.'});qa.raise_for_status()
    report={'run':run_id,'initial_audit':initial,'cases':cases,'final_audit':audit,'chat':chat.json(),'photo_qa':qa.json(),'exports_and_photo_hashes_verified':4}
    (ROOT/'tests/artifacts/audit-live.json').write_text(json.dumps(report,indent=2));print('Live audit completed.',flush=True)
