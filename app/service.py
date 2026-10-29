"""Node 2 policy/text inference and Node 3 vision inference entry points."""
import argparse,base64,binascii,os,secrets,time
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import JSONResponse,FileResponse
from pydantic import Field
from .domain import StrictModel,Observation,Product
from .images import validate_photo
from .models import LocalModels,ModelBusy,ModelUnavailable
from .policy import Policies
from .nodes import PORTS

class InspectInput(StrictModel):
    image:str=Field(max_length=14*1024*1024)
    budget:float=Field(gt=0,le=240,allow_inf_nan=False)
class TextInput(StrictModel):
    prompt:str=Field(min_length=1,max_length=32000)
    image:str|None=Field(default=None,max_length=14*1024*1024)
class SearchInput(StrictModel):
    query:str=Field(max_length=3000)
    manufacturer:str=Field(max_length=64)
    product_type:Product
    limit:int=Field(default=5,ge=1,le=10)
class PolicyCase(StrictModel):
    product_name:str=Field(max_length=128)
    manufacturer:str=Field(max_length=64)
    product_type:Product
class EvaluateInput(StrictModel):
    case:PolicyCase
    observations:list[Observation]=Field(min_length=1,max_length=5)

class InternalBoundary:
    def __init__(self,app,token):self.app=app;self.token=token
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        request=Request(scope)
        if not request.client or request.client.host not in {'127.0.0.1','::1','testclient'}:
            return await JSONResponse({'detail':'Loopback access only.'},status_code=403)(scope,receive,send)
        if scope['path']!='/health' and not secrets.compare_digest(request.headers.get('x-happy-node-token',''),self.token):
            return await JSONResponse({'detail':'Internal node authentication required.'},status_code=401)(scope,receive,send)
        size=0
        async def bounded():
            nonlocal size
            message=await receive();size+=len(message.get('body',b''))
            if size>15*1024*1024:raise HTTPException(413,'Internal request too large.')
            return message
        await self.app(scope,bounded,send)

def decode(value):
    try:
        raw=base64.b64decode(value,validate=True);validate_photo(raw,0,'internal-photo',10*1024*1024);return raw
    except (ValueError,binascii.Error):raise HTTPException(422,'Invalid internal raster image.')

def create_service(role,token=None,models=None,policies=None):
    if role not in {'policy','vision'}:raise ValueError('Unsupported service role')
    token=token or os.environ.get('HAPPY_NODE_TOKEN','')
    if len(token)<32:raise RuntimeError('A private internal node token is required.')
    app=FastAPI(title='SmartRMA '+role+' node',docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(InternalBoundary,token=token)
    models=models or LocalModels(role=role)
    policies=policies or (Policies() if role=='policy' else None)
    @app.exception_handler(ModelBusy)
    async def busy(request,exc):return JSONResponse({'detail':str(exc)},status_code=409)
    @app.exception_handler(ModelUnavailable)
    async def unavailable(request,exc):return JSONResponse({'detail':str(exc)},status_code=503)
    @app.get('/health')
    def health():return {'status':'ok','application':'happy_project','role':role,'port':PORTS[role]}
    @app.get('/models')
    def inventory():return models.health()
    if role=='vision':
        @app.post('/inspect')
        def inspect(body:InspectInput):
            obs,model=models.inspect(decode(body.image),time.monotonic()+body.budget)
            return {'observation':obs.model_dump(),'model':model}
        @app.post('/text')
        def text(body:TextInput):
            if body.image is None:raise HTTPException(422,'Policy text requests belong to Node 2.')
            result,model=models.text(body.prompt,decode(body.image))
            return {'result':result,'model':model}
    else:
        @app.get('/catalog')
        def catalog():return policies.catalog()
        @app.post('/search')
        def search(body:SearchInput):return {'sources':policies.search(body.query,body.manufacturer,body.product_type.value,body.limit)}
        @app.post('/evaluate')
        def evaluate(body:EvaluateInput):return policies.evaluate(body.case.model_dump(mode='json'),body.observations)
        @app.get('/document/{name}')
        def document(name:str):
            try:path=policies.document(name)
            except FileNotFoundError:raise HTTPException(404,'Document not found.')
            return FileResponse(path,media_type='application/pdf' if path.suffix.lower()=='.pdf' else 'text/plain')
        @app.post('/text')
        def text(body:TextInput):
            if body.image is not None:raise HTTPException(422,'Image questions belong to Node 3.')
            result,model=models.text(body.prompt)
            return {'result':result,'model':model}
    return app

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--role',choices=['policy','vision'],required=True);args=parser.parse_args()
    import uvicorn
    uvicorn.run(create_service(args.role),host='127.0.0.1',port=PORTS[args.role],workers=1,proxy_headers=False,server_header=False,log_level='warning')
if __name__=='__main__':main()
