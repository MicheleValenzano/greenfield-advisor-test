from fastapi import HTTPException
import os
import jwt

PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "PUBLIC_KEY").replace("\\n", "\n")

ALGORITHM = "RS256"

def verify_jwt_token(auth_header: str) -> bool:
    """
    Verifica il token JWT dall'header di autorizzazione.
    Returns:
        bool: True se il token è valido.
    Raises:
        HTTPException: Se il token è mancante, scaduto o non valido.
    """
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header mancante.")
    
    try:
        token_type, token = auth_header.split()
        if token_type.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Tipo di token non supportato.")
        
        if not token:
            raise HTTPException(status_code=401, detail="Token di autorizzazione mancante.")

        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token di accesso scaduto.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token di accesso non valido.")
    except Exception as e:
        print(f"Errore nella verifica del token: {e}")
        raise HTTPException(status_code=401, detail="Errore nella verifica del token di accesso.")
    
    return True