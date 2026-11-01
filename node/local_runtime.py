"""Shared local-only inference, image validation, and HTTP protections."""
import base64
import io
import json
import os
import time
import threading
import urllib.request
import urllib.error
from urllib.parse import urlsplit
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

BASE_DIR = Path(__file__).resolve().parent.parent
OLLAMA_URL = 'http://127.0.0.1:11434'
# Ignore system proxy settings: image/text payloads must remain on loopback.
class LoopbackRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if target.scheme != 'http' or target.hostname not in {'127.0.0.1', 'localhost'}:
            raise urllib.error.HTTPError(newurl, code, 'Remote redirects are forbidden for local inference', headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

LOCAL_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}), LoopbackRedirectHandler())
CHAT_MODELS = ['qwen2.5:7b', 'qwen2.5-coder:14b', 'ornith:35b', 'llama3.1:8b']
VISION_MODELS = ['qwen3-vl:8b', 'llama3.2-vision:latest', 'moondream:latest']
VISION_REQUEST_SECONDS = 240
VISION_ATTEMPT_SECONDS = 70
GATEWAY_VISION_SECONDS = VISION_REQUEST_SECONDS + 15
CHAT_REQUEST_SECONDS = 180
ROUTE_REQUEST_SECONDS = GATEWAY_VISION_SECONDS + 30
MODEL_STATE = {}
MODEL_STATE_LOCK = threading.Lock()

ALLOWED_ORIGINS = ['http://127.0.0.1:8001', 'http://localhost:8001']

class LocalAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Block foreign browser origins on mutations; API clients without Origin work locally.
        origin = request.headers.get('origin')
        if request.method not in {'GET', 'HEAD', 'OPTIONS'} and origin and origin not in ALLOWED_ORIGINS:
            return JSONResponse({'detail': 'Only the local SmartRMA portal may change data.'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'same-origin'
        return response

def local_json(path, payload=None, timeout=120):
    if not path.startswith('/api/') or '..' in path:
        raise ValueError('Invalid local Ollama endpoint')
    request = urllib.request.Request(OLLAMA_URL + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Content-Type': 'application/json'})
    with LOCAL_HTTP.open(request, timeout=timeout) as response:
        return json.load(response)

def installed_models():
    try:
        return [m['name'] for m in local_json('/api/tags', timeout=3).get('models', [])
                if not m.get('remote_host') and ':cloud' not in m.get('name', '')]
    except Exception:
        return []

def available_models(preferences):
    installed = installed_models()
    return [m for m in preferences if m in installed]

def safe_image_path(path_str):
    if not path_str or '..' in path_str:
        return None
    path = Path(path_str)
    candidate = (BASE_DIR / path).resolve() if not path.is_absolute() else path.resolve()
    if not candidate.is_relative_to(BASE_DIR):
        return None
    if candidate.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}:
        return None
    return str(candidate) if candidate.is_file() else None

def decode_image(image_b64=None, url=None):
    try:
        if image_b64:
            data = base64.b64decode(image_b64.split(',')[-1], validate=True)
        elif url:
            path = safe_image_path(url)
            if not path:
                raise ValueError('Invalid image path')
            if os.path.getsize(path) > 15 * 1024 * 1024:
                raise ValueError('Image exceeds 15MB')
            data = Path(path).read_bytes()
        else:
            raise ValueError('Image data is required')
        if len(data) > 15 * 1024 * 1024:
            raise ValueError('Image exceeds 15MB')
        image = Image.open(io.BytesIO(data))
        if image.width * image.height > 25_000_000:
            raise ValueError('Image exceeds 25 megapixels')
        image.load()
        return image, data
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise HTTPException(status_code=400, detail=f'Invalid inspection image: {exc}') from exc


def record_model_result(model, success, detail=None):
    with MODEL_STATE_LOCK:
        MODEL_STATE[model] = {'state': 'ready' if success else 'failed',
                              'detail': detail, 'checked_at': time.time()}

def model_readiness(models):
    with MODEL_STATE_LOCK:
        states = {model: MODEL_STATE.get(model, {'state': 'untested'}) for model in models}
    ready = any(value['state'] == 'ready' for value in states.values())
    return {'inference_ready': ready, 'inference_state': 'ready' if ready else
            'untested' if any(v['state'] == 'untested' for v in states.values()) else 'unavailable',
            'model_status': states}
