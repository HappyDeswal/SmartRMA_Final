"""Offline PDF indexing. Never downloads documents or sends their contents out."""
import hashlib,json,os,re,tempfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from pypdf import PdfReader
from .policy import detect_brand

def rebuild(root):
    root=Path(root);previous=json.loads((root/'index.json').read_text()) if (root/'index.json').exists() else {}
    known={d['filename']:d for d in previous.get('catalog',[])}
    chunks=[];catalog=[];failures=[]
    for path in sorted([*root.glob('*.pdf'),*root.glob('*.md')]):
        try:
            pages=[p.extract_text() or '' for p in PdfReader(path).pages] if path.suffix.lower()=='.pdf' else [path.read_text()]
            manufacturer=known.get(path.name,{}).get('manufacturer') or detect_brand(path.stem) or 'Universal Hardware'
            start=len(chunks);scope='processor' if re.search(r'processor|ryzen',path.name,re.I) else None
            for page_no,page in enumerate(pages,1):
                text=' '.join(page.split())
                for offset in range(0,len(text),800):
                    passage=text[offset:offset+1000]
                    if len(passage)<30:continue
                    category='exclusion_cid' if re.search(r'physical damage|customer.induced|misuse|abuse|corrosion',passage,re.I) else 'general_terms'
                    item={'id':f'{path.name}:p{page_no}:{offset}','manufacturer':manufacturer,'source_file':path.name,'page':page_no,'total_pages':len(pages),'category':category,'text':passage}
                    if scope:item['product_scope']=scope
                    chunks.append(item)
            if len(chunks)==start:raise ValueError('No selectable text; OCR is required offline before indexing.')
            catalog.append({'filename':path.name,'type':'PDF' if path.suffix.lower()=='.pdf' else 'Markdown','manufacturer':manufacturer,'pages':len(pages),'chunks':len(chunks)-start,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        except Exception as exc:failures.append({'file':path.name,'error':type(exc).__name__})
    if failures:raise ValueError('Index left unchanged because documents failed: '+json.dumps(failures))
    if not catalog:raise ValueError('No readable policy PDFs found; index left unchanged.')
    data={'metadata':{'version':'happy-1','created':datetime.now(timezone.utc).isoformat(),'indexed_documents':len(catalog),'total_chunks':len(chunks),'manufacturers':sorted({d['manufacturer'] for d in catalog}),'failed_documents':[],'distribution':dict(Counter(c['manufacturer'] for c in chunks))},'catalog':catalog,'chunks':chunks}
    fd,temp=tempfile.mkstemp(prefix='.index-',dir=root)
    try:
        with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
        os.replace(temp,root/'index.json')
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return data['metadata']
