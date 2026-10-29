import base64,hashlib,io,warnings
from PIL import Image,ImageOps,UnidentifiedImageError
import imagehash

MIMES={'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp','BMP':'image/bmp'}

def validate_photo(raw,slot,name,max_bytes):
    if not raw or len(raw)>max_bytes: raise ValueError('Each photo must be nonempty and at most 10 MiB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as check:
                if getattr(check,'n_frames',1)!=1:raise ValueError('Use a single-frame original photo; animated images are not supported.')
                if check.format not in MIMES: raise ValueError('Use JPEG, PNG, WebP or BMP raster photos.')
                if check.width*check.height>25_000_000: raise ValueError('Photo exceeds 25 megapixels.')
                check.verify()
            with Image.open(io.BytesIO(raw)) as source:
                source.load();software=str(source.getexif().get(305,''))[:256]
                oriented=ImageOps.exif_transpose(source).convert('RGB')
                digest=str(imagehash.phash(oriented))
                width,height=oriented.size
                mime=MIMES[source.format]
        return {'id':hashlib.sha256(raw).hexdigest(),'raw':raw,'slot':slot,'name':name[:120],
                'mime':mime,'bytes':len(raw),'width':width,'height':height,'phash':digest,
                'software':software,'edited':any(x in software.casefold() for x in ['photoshop','gimp','lightroom','canva','snapseed','pixelmator'])}
    except (OSError,UnidentifiedImageError,Image.DecompressionBombError,Image.DecompressionBombWarning) as exc:
        raise ValueError('The image is invalid or exceeds safe decoder limits.') from exc

def vision_copy(raw):
    with Image.open(io.BytesIO(raw)) as source:
        source.load();image=ImageOps.exif_transpose(source).convert('RGB');image.thumbnail((1280,1280))
        out=io.BytesIO();image.save(out,format='JPEG',quality=90)
        return base64.b64encode(out.getvalue()).decode()

def similar_hash(a,b): return (int(a,16)^int(b,16)).bit_count()<=4
