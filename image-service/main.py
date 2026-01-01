from fastapi import FastAPI, File, UploadFile, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
import numpy as np
from rasterio.io import MemoryFile
import matplotlib.pyplot as plt
import io
import base64
import os
import jwt

plt.switch_backend('Agg')

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "PUBLIC_KEY")
PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEApXtfAxVV015pQOx026do
IkRAVcRW9VieD0DSvP4PxQl055CBnJh42DrdshKWNvfSJ98OxH5Hz9WGMQHit1hQ
HJwAC0/bue2sa5HoaH/0o7eyFVYnui+3YrYOYO/a2zG4qiSmkVwvOy/L+uymaAjl
Y4fGzcf8TRMWEUZ7A4pIhvTuSMgRDyobVVmoBiKzvbAPqs3ggP8Vmd//hXovaSww
JugwkvSVQvDaeRjKk2ENbwrA85BxtblE/sA1OKN0RQo1jkOECKuhi9nPhrRrtMs8
MChlLW9GrBagFZVFA9LCTCSAXIWlzQIWNhUlh96/ih12KG3ynuXxxuggF9GeWLUl
jtTXJSY6LyHmsRUsgC17S7sTyIYXmW4gJj4qXWGeVqRwsPj+aWQBYyi5IyBXH7gV
iqJT39xgWLl81dYpO7B0Jx4zIc9MfYltsXXUxFDRuOftDQKKJ4bKDIdbjko3giUC
A2LY9dJjJXB4j5wovqVJnDU4vrdgGmxZklRoaQq0dkWlhGAH982cQ1A6mfEOsDgc
yO5xVZNmlQ7cVuNjyZ1Wr1Hcc4UYNSibzx6Y+8C4/x6jBodBxHofAPYR/jrFoLAu
ACgboGEVD48oNVAd7XRnjXcOvu+kvRhLjwO6VoOJeRfArPAkXmL7pelkqY5RFcvg
h8XIDNY39jp5TDH4Pa8/Q8MCAwEAAQ==
-----END PUBLIC KEY-----"""

ALGORITHM = "RS256"

app = FastAPI(title="Image Service")

def decode_access_token(jwt_token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(jwt_token, PUBLIC_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token di accesso scaduto.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token di accesso non valido.")

def calculate_ndvi(red_band, nir_band):
    ndvi = (nir_band - red_band) / (nir_band + red_band + 1e-10)
    return ndvi

def ndvi_to_png_with_legend(ndvi: np.ndarray) -> io.BytesIO:
    ndvi_normalidzed = (ndvi + 1) / 2
    ndvi_normalidzed = np.clip(ndvi_normalidzed, 0, 1)

    cmap = plt.get_cmap('RdYlGn')

    fig, ax = plt.subplots(figsize=(8, 6))
    img = ax.imshow(ndvi_normalidzed, cmap=cmap, vmin=0, vmax=1)
    ax.axis('off')
    ax.set_title('NDVI index')

    ticks = [0, 0.25, 0.5, 0.75, 1]

    cbar = fig.colorbar(img, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_ticks(ticks)
    cbar.set_ticklabels(['-1.0', '-0.5', '0.0', '0.5', '1.0'])

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buffer.seek(0)

    return buffer

def png_to_base64(png_buffer: io.BytesIO) -> str:
    return base64.b64encode(png_buffer.getvalue()).decode('utf-8')

def ndvi_description(ndvi: np.ndarray) -> str:
    mean_ndvi = np.nanmean(ndvi)
    if mean_ndvi < 0:
        return "La vegetazione è scarsa o assente."
    elif 0 <= mean_ndvi < 0.2:
        return "La vegetazione è molto scarsa."
    elif 0.2 <= mean_ndvi < 0.4:
        return "La vegetazione è scarsa."
    elif 0.4 <= mean_ndvi < 0.6:
        return "La vegetazione è moderata."
    elif 0.6 <= mean_ndvi < 0.8:
        return "La vegetazione è alta."
    else:
        return "La vegetazione è molto alta."

"""
@app.post("/compute-ndvi/png")
async def compute_ndvi_png(file: UploadFile = File(...), token: dict = Depends(decode_access_token)):

    if not file.filename.lower().endswith(('.tif', '.tiff')):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo di file non valido. Sono amessi solo .tif e .tiff.")
    
    data = await file.read()

    with MemoryFile(data) as memfile:
        with memfile.open() as dataset:
            if dataset.count < 4:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Il file TIFF deve contenere almeno 4 bande (inclusi Red e NIR).")
            
            red_band = dataset.read(3).astype('float32')
            nir_band = dataset.read(4).astype('float32')

    ndvi = calculate_ndvi(red_band, nir_band)
    png_buffer = ndvi_to_png_with_legend(ndvi)
    
    png_buffer.seek(0)
    return StreamingResponse(png_buffer, media_type="image/png")
"""
    
@app.post("/compute-ndvi")
async def compute_ndvi(file: UploadFile = File(...), token: dict = Depends(decode_access_token)):
    if not file.filename.lower().endswith(('.tif', '.tiff')):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo di file non valido. Sono amessi solo .tif e .tiff.")
    
    try:
        data = await file.read()

        with MemoryFile(data) as memfile:
            with memfile.open() as dataset:
                if dataset.count < 4:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Il file TIFF deve contenere almeno 4 bande (inclusi Red e NIR).")
                
                red_band = dataset.read(3).astype('float32')
                nir_band = dataset.read(4).astype('float32')

        ndvi = calculate_ndvi(red_band, nir_band)
        png_buffer = ndvi_to_png_with_legend(ndvi)

        base64_png = png_to_base64(png_buffer)
        description = ndvi_description(ndvi)

        return {
            "filename": file.filename,
            "description": description,
            "mean_ndvi": float(np.nanmean(ndvi)),
            "ndvi_image_base64": base64_png
        }
    
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Errore nell'elaborazione dell'immagine.")