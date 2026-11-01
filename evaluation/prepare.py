"""Prepare unlabelled review pools; never derive damage ground truth from a model or filename."""
import argparse,hashlib,json,random
from pathlib import Path
from zipfile import ZipFile

BRANDS=['NVIDIA','ASUS','GIGABYTE','EVGA','Dell','Apple','Acer','Lenovo','HP']
QUESTIONS=[
 'What purchase documents are required for a warranty claim?',
 'Does the warranty cover accidental liquid spills?',
 'Is damage caused during installation covered?',
 'What warranty exclusions apply to a cracked board?',
 'Does removing or damaging the serial label affect eligibility?',
 'What packaging is required when shipping a return?',
 'Who pays shipping charges for a warranty return?',
 'What steps must I follow before sending hardware for repair?',
 'Does the warranty transfer to a second owner?',
 'What geographical restrictions apply to warranty service?',
 'Can an unauthorized repair affect warranty coverage?',
 'Are normal wear and cosmetic scratches covered?',
 'How is the warranty period determined?',
 'What remedies are available for a qualifying defect?',
 'Are accessories and consumables covered on the same terms?',
 'Can photographs alone establish the purchase date?',
 'Does a warranty automatically entitle me to a cash refund?']

def write_page(template,payload,destination):
    data=json.dumps(payload,ensure_ascii=True).replace('<','\\u003c')
    destination.write_text(template.read_text().replace('__REVIEW_DATA__',data))

def prepare(source,index,output,count=250):
    output=Path(output)
    if output.exists():raise ValueError('Choose a new review directory; existing annotations are never overwritten')
    output.mkdir(parents=True);rng=random.Random(42)
    with ZipFile(source) as z:
        manifest=json.loads(z.read('data/hardware/manifest.json'));selected=[]
        buckets={label:[r for r in manifest if r['label']==label] for label in ['graphics_card','motherboard','ram','ssd']}
        for b in buckets.values():rng.shuffle(b)
        while len(selected)<count and any(buckets.values()):
            for bucket in buckets.values():
                if bucket and len(selected)<count:selected.append(bucket.pop())
        if len(selected)!=count:raise ValueError('Insufficient source images')
        rows=[]
        for r in selected:
            raw=z.read('data/hardware/'+r['path']);assert hashlib.sha256(raw).hexdigest()==r['sha256']
            dest=output/r['path'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
            rows.append({**r,'id':r['sha256'],'source_product_type':r['label'],'product_type':None,'damage_label':None,'physical_item_id':None,'reviewer':'','review_state':'pending','notes':'','roi':None,'calibration_mm_per_pixel':None,'evaluation_split':'unassigned'})
    policy=json.loads(Path(index).read_text());queries=[]
    for i in range(150):
        brand=BRANDS[i%len(BRANDS)];text=QUESTIONS[i//len(BRANDS)]
        queries.append({'id':f'policy-{i+1:03d}','manufacturer':brand,'query':brand+': '+text,'answerable':None,'relevant_chunk_ids':[],'reviewer':'','review_state':'pending','notes':'','evaluation_split':'unassigned'})
    (output/'image_annotations.json').write_text(json.dumps(rows,indent=2))
    (output/'policy_annotations.json').write_text(json.dumps(queries,indent=2))
    templates=Path(__file__).parent/'templates'
    write_page(templates/'images.html',rows,output/'review_images.html')
    write_page(templates/'policies.html',{'queries':queries,'chunks':policy['chunks']},output/'review_policies.html')
    summary={'seed':42,'image_count':len(rows),'policy_queries':len(queries),'manufacturers':BRANDS,'damage_labels_verified':0,'policy_gold_labels_verified':0,'physical_item_independence':'unknown; reviewer IDs required before split','image_sha256_verified':True,'policy_index_sha256':hashlib.sha256(Path(index).read_bytes()).hexdigest(),'purpose':'annotation_pool_not_a_validated_test_set','warning':'Original source product labels are unverified; no damage labels inferred. The pool may lack enough real defects. Collect additional verified defect examples after review. Do not tune on final test annotations.'}
    (output/'preparation.json').write_text(json.dumps(summary,indent=2))
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--index',default='policy/policy_index.json');p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(prepare(a.source,a.index,a.output),indent=2))
