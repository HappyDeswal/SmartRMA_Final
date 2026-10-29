"""Authenticated loopback transport between the three local application nodes."""
import base64,os,time
from dataclasses import dataclass
import httpx
from .domain import Observation
from .models import LocalModels,ModelBusy,ModelUnavailable

PORTS={'gateway':8010,'policy':8011,'vision':8012}
class NodeUnavailable(ModelUnavailable):pass
@dataclass
class RemoteDocument:
    name:str
    data:bytes
    mime:str

class NodeTransport:
    def __init__(self,role,token=None):self.role=role;self.port=PORTS[role];self.token=token or os.environ.get('HAPPY_NODE_TOKEN','')
    def call(self,path,payload=None,timeout=10,raw=False):
        if not path.startswith('/') or path.startswith('//'):raise ValueError('Invalid internal route')
        if not self.token:raise NodeUnavailable('Internal service credentials are missing.')
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{self.port}',trust_env=False,follow_redirects=False,timeout=timeout) as c:
                r=c.post(path,json=payload,headers={'X-Happy-Node-Token':self.token}) if payload is not None else c.get(path,headers={'X-Happy-Node-Token':self.token})
                if r.status_code==409:raise ModelBusy('The local inference node is busy.')
                if r.status_code==404:raise FileNotFoundError('Source document not found.')
                r.raise_for_status()
                if r.is_redirect:raise NodeUnavailable('Internal redirects are refused.')
                if raw:return r
                data=r.json()
                if not isinstance(data,dict):raise ValueError('Invalid internal response object')
                return data
        except (httpx.HTTPError,ValueError) as exc:raise NodeUnavailable(f'The local {self.role} node is unavailable. Check the three-node launcher.') from exc
    def health(self):
        try:return {**self.call('/health',timeout=2),'reachable':True}
        except (NodeUnavailable,FileNotFoundError):return {'role':self.role,'port':self.port,'reachable':False,'status':'unavailable'}

class RemoteModels:
    inconclusive=staticmethod(LocalModels.inconclusive)
    def __init__(self):self.vision=NodeTransport('vision');self.policy=NodeTransport('policy')
    def health(self):
        inventories={};errors={}
        for role,node in [('vision',self.vision),('policy',self.policy)]:
            try:inventories[role]=node.call('/models',timeout=5)
            except NodeUnavailable:inventories[role]={};errors[role]=f'{role} node unavailable'
        vision= inventories['vision'];policy=inventories['policy']
        return {'provider':'local_ollama','endpoint':'http://127.0.0.1:11434',
                'vision_candidates':vision.get('vision_candidates',[]),'chat_candidates':policy.get('chat_candidates',[]),
                'model_states':{**vision.get('model_states',{}),**policy.get('model_states',{})},
                'inference_tested':bool(vision.get('inference_tested') or policy.get('inference_tested')),
                'busy':bool(vision.get('busy') or policy.get('busy')),
                'hardware_classifier':vision.get('hardware_classifier'),
                'execution_nodes':{'vision':'Node 3','policy_chat':'Node 2'},'node_errors':errors}
    def inspect(self,raw,deadline):
        budget=max(0,deadline-time.monotonic())
        if budget<=0:return self.inconclusive('Inspection budget exhausted.'),None
        result=self.vision.call('/inspect',{'image':base64.b64encode(raw).decode(),'budget':budget},timeout=budget+5)
        return Observation.model_validate(result['observation']),result['model']
    def text(self,prompt,vision_raw=None):
        node=self.vision if vision_raw is not None else self.policy
        payload={'prompt':prompt,'image':base64.b64encode(vision_raw).decode() if vision_raw is not None else None}
        result=node.call('/text',payload,timeout=130)
        return result['result'],result['model']

class RemotePolicies:
    def __init__(self):self.node=NodeTransport('policy')
    @property
    def files(self):
        try:return {r['filename'] for r in self.catalog()['documents']}
        except NodeUnavailable:return set()
    def catalog(self):return self.node.call('/catalog')
    def search(self,query,manufacturer,product_type,limit=5):return self.node.call('/search',{'query':query,'manufacturer':manufacturer,'product_type':product_type,'limit':limit})['sources']
    def evaluate(self,case,observations):
        return self.node.call('/evaluate',{'case':{k:case[k] for k in ['product_name','manufacturer','product_type']},'observations':[o.model_dump() for o in observations]})
    def document(self,name):
        from urllib.parse import quote
        r=self.node.call('/document/'+quote(name,safe=''),raw=True)
        return RemoteDocument(name,r.content,r.headers['content-type'])
