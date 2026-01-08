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

# Utilizzo del backend 'Agg' per matplotlib per evitare problemi in ambienti senza display
plt.switch_backend('Agg')

# Configurazione OAuth2 per ottenere il token jwt negli endpoint automaticamente
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "PUBLIC_KEY").replace("\\n", "\n")

ALGORITHM = "RS256"

app = FastAPI(title="Image Service")

def decode_access_token(jwt_token: str = Depends(oauth2_scheme)):
    """
    Decodifica e verifica il token di accesso JWT.
    Args:
        jwt_token (str): Il token JWT da decodificare.
    Returns:
        dict: Il payload decodificato del token JWT.
    Raises:
        HTTPException: Se il token è scaduto o non valido.
    """
    try:
        payload = jwt.decode(jwt_token, PUBLIC_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token di accesso scaduto.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token di accesso non valido.")

def calculate_ndvi(red_band, nir_band):
    """
    Calcola l'indice NDVI a partire dalle bande Red e NIR.
    Args:
        red_band (np.ndarray): Banda Red dell'immagine.
        nir_band (np.ndarray): Banda NIR dell'immagine.
    Returns:
        np.ndarray: Matrice NDVI calcolata.
    """
    ndvi = (nir_band - red_band) / (nir_band + red_band + 1e-10)
    return ndvi

def ndvi_to_png_with_legend(ndvi: np.ndarray) -> io.BytesIO:
    """
    Converte una matrice NDVI in un'immagine PNG con legenda.
    Args:
        ndvi (np.ndarray): Matrice NDVI.
    Returns:
        io.BytesIO: Buffer contenente l'immagine PNG.
    """
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
    """
    Converte un'immagine PNG in una stringa base64.
    Args:
        png_buffer (io.BytesIO): Buffer contenente l'immagine PNG.
    Returns:
        str: Stringa base64 dell'immagine PNG.
    """
    return base64.b64encode(png_buffer.getvalue()).decode('utf-8')

def ndvi_description(ndvi: np.ndarray) -> str:
    """
    Fornisce una descrizione testuale basata sul valore medio dell'NDVI.
    Args:
        ndvi (np.ndarray): Matrice NDVI.
    Returns:
        str: Descrizione della vegetazione basata sull'NDVI medio."""
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
    
@app.post("/compute-ndvi")
async def compute_ndvi(file: UploadFile = File(...), token: dict = Depends(decode_access_token)):
    """
    Calcola l'NDVI da un file TIFF caricato e restituisce l'immagine PNG codificata in base64 insieme a una descrizione testuale.
    Args:
        file (UploadFile): File TIFF caricato.
        token (dict): Payload del token di accesso decodificato.
    Returns:
        dict: Dizionario contenente il nome del file, la descrizione, l'NDVI medio e l'immagine NDVI in formato base64.
    Raises:
        HTTPException: In caso di errori durante l'elaborazione del file.
    """
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