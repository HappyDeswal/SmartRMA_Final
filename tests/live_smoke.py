"""Opt-in live local Ollama check. Creates clearly labelled demo cases; never decides T4."""
import json,time,uuid
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
client=httpx.Client(base_url='http://127.0.0.1:8010',timeout=150,trust_env=False)
credentials=json.loads((ROOT/'var/first_login.json').read_text())
auth=client.post('/api/auth/login',json={k:credentials[k] for k in ['username','password']});auth.raise_for_status()
headers={'X-CSRF-Token':auth.json()['csrf']}
rows=json.loads((ROOT/'sample_data/manifest.json').read_text());cases=[]
for level,product in [('T1','graphics_card'),('T2','motherboard'),('T3','ram'),('T4','ssd')]:
    order='HAPPY-LIVE-'+level
    old=client.get('/api/cases',params={'search':order}).json()['items']
    if old:ident=old[0]['id']
    else:
        item=next(r for r in rows if r['tier']==level and r['product_type']==product)
        metadata={'order_id':order,'product_type':product,'product_name':item['product_name']+' · live smoke','manufacturer':'Unknown','value':str(item['price_USD']),'complaint':'Live software verification with licensed sample photo and synthetic price.','slots':[0]}
        response=client.post('/api/cases',data={'metadata':json.dumps(metadata)},files={'photos':('original.jpg',(ROOT/'sample_data'/item['file']).read_bytes(),'image/jpeg')},headers={**headers,'Idempotency-Key':'live-'+uuid.uuid4().hex});response.raise_for_status();ident=response.json()['case_id']
    cases.append(ident)
limit=time.monotonic()+1000
while time.monotonic()<limit:
    results=[client.get('/api/cases/'+ident).json() for ident in cases]
    print([(c['tier'],c['status'],c['job']['stage']) for c in results],flush=True)
    if all(c['job']['status'] in {'complete','failed'} for c in results):break
    time.sleep(10)
assert all(c['job']['status']=='complete' for c in results),results
assert results[-1]['status']=='needs_review'
assert all(c['status'] in {'approved','rejected'} for c in results[:-1])
report={'cases':[{k:c[k] for k in ['id','tier','status','decision','observations']} for c in results],'audit':client.get('/api/audit/verify').json()}
assert report['audit']['valid']
for c in results:
    exported=client.get('/api/cases/'+c['id']+'/export');exported.raise_for_status()
report['exports_verified']=len(results)
chat=client.post('/api/chat',headers=headers,json={'message':'What can photos establish about whether RAM works electrically?'});chat.raise_for_status();report['chat']=chat.json()
qa=client.post('/api/vision/question',headers=headers,json={'image_id':results[0]['photos'][0]['id'],'question':'Describe the visible connectors, without inferring electrical function.'});qa.raise_for_status();report['photo_qa']=qa.json()
(ROOT/'tests/artifacts/live.json').write_text(json.dumps(report,indent=2));print('Live tests complete.',flush=True)
