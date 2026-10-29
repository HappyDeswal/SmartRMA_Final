import json,re
from pathlib import Path
from .config import ROOT

ALIASES={'gigabyte':'GIGABYTE','aorus':'GIGABYTE','asus':'ASUS','rog':'ASUS','tuf':'ASUS','msi':'MSI','evga':'EVGA',
         'nvidia':'NVIDIA','geforce':'NVIDIA','amd':'AMD','radeon':'AMD','intel':'Intel','apple':'Apple','dell':'Dell',
         'acer':'Acer','lenovo':'Lenovo','hp':'HP','corsair':'Corsair','samsung':'Samsung','micron':'Micron',
         'kingston':'Kingston','crucial':'Crucial','sandisk':'SanDisk','g.skill':'G.Skill'}
CHIP={'NVIDIA','AMD','Intel'}

def brand(value): return ALIASES.get(value.strip().casefold(),value.strip())
def detect_brand(text):
    found={v for k,v in ALIASES.items() if re.search(r'(?<!\w)'+re.escape(k)+r'(?!\w)',text,re.I)}
    boards=found-CHIP
    if boards:return next(iter(boards)) if len(boards)==1 else None
    if len(found)==1:return next(iter(found))
    if not found and re.search(r'\brtx\b',text,re.I):return 'NVIDIA'
    return None

def terms(text):return set(re.findall(r'[a-z0-9]{2,}',text.casefold()))

class Policies:
    def __init__(self,root=None):
        self.root=Path(root or ROOT/'resources/policies')
        path=self.root/'index.json'
        self.data=json.loads(path.read_text()) if path.exists() else {'metadata':{},'catalog':[],'chunks':[]}
        self.files={r['filename'] for r in self.data.get('catalog',[])}

    def catalog(self):return {'metadata':self.data.get('metadata',{}),'documents':self.data.get('catalog',[])}

    def search(self,query,manufacturer,product_type,limit=5):
        target=brand(manufacturer)
        if target.casefold() in {'unknown','unverified','other',''}:return []
        words=terms(query);ranked=[]
        for chunk in self.data.get('chunks',[]):
            if brand(chunk.get('manufacturer',''))!=target:continue
            filename=Path(chunk.get('source_file','')).name
            if filename not in self.files:continue
            scope=chunk.get('product_scope','')
            # Processor-only warranties cannot apply to the four supported product classes.
            if scope=='processor' or re.search(r'\b(processor|processors|ryzen)\b',filename,re.I):continue
            score=len(words & terms(chunk.get('text','')))
            if not score:continue
            ranked.append((score,chunk,filename))
        ranked.sort(key=lambda x:x[0],reverse=True)
        results=[];seen=set()
        for score,c,filename in ranked:
            key=(filename,c.get('page'),c.get('text'))
            if key in seen:continue
            seen.add(key);results.append({'document':filename,'page':c.get('page'),'excerpt':c['text'][:900],
                'manufacturer':c.get('manufacturer'),'category':c.get('category'),'score':score})
            if len(results)>=limit:break
        return results

    def evaluate(self,case,observations):
        damaged=any(o.condition in {'physical_damage','tampered'} for o in observations)
        query=case['product_name']+' '+('physical damage customer induced burn corrosion exclusion' if damaged else 'warranty manufacturing defect replacement')
        sources=self.search(query,case['manufacturer'],case['product_type'])
        exclusion=next((s for s in sources if s['category']=='exclusion_cid'),None)
        return {'grounded':bool(sources),'excluded':bool(damaged and exclusion),'sources':sources,
                'advisory':True,'notice':'Indexed terms are advisory; regional and purchase-date eligibility is not established.'}

    def document(self,name):
        if name not in self.files or Path(name).name!=name:raise FileNotFoundError
        path=self.root/name
        if not path.is_file() or path.suffix.lower() not in {'.pdf','.md'}:raise FileNotFoundError
        return path
