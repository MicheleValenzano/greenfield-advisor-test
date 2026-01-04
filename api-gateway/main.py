from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, WebSocketException, Depends
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import websockets
from config import ROUTE_MAP, SERVICE_URLS, PUBLIC_PATHS, REDIS_URL
from auth import verify_jwt_token
from proxy import proxy_request
import redis.asyncio as aioredis
import asyncio
from typing import Optional

app = FastAPI(title="API Gateway")

async def check_ws_rate_limit(redis_client, key: str, limit: int, window: int):
    """
    Rate Limiter manuale per WebSocket.
    Parametri:
    redis_client: Istanza del client Redis.
    key: Chiave unica per l'utente (es. ID utente).
    limit: Numero massimo di connessioni consentite nella finestra di tempo.
    window: Finestra di tempo in secondi.
    Solleva HTTPException(409) se il limite viene superato.
    """
    if not redis_client:
        return # Se Redis non è disponibile, non applicare il rate limit
    
    redis_key = f"ws_ratelimit:{key}"

    # Incrementa il contatore
    current_count = await redis_client.incr(redis_key)

    # Se è il primo accesso, imposta la scadenza
    if current_count == 1:
        await redis_client.expire(redis_key, window)
    
    # Se il conteggio supera il limite, solleva un'eccezione
    if current_count > limit:
        raise HTTPException(status_code=429, detail="Troppe richieste (riprova più tardi).")


def resolve_service(path: str) -> Optional[str]:
    matches = [prefix for prefix in ROUTE_MAP if path == prefix or path.startswith(f"{prefix}/")]
    if not matches:
        return None
    return ROUTE_MAP[max(matches, key=len)]

@app.on_event("startup")
async def startup_event():
    """
    Evento di startup per inizializzare la connessione a Redis per il rate limiting.
    """
    try:
        # Connessione a redis per il rate limiting
        redis_client = aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)

        # Inizializzo il limiter per le richieste HTTP
        await FastAPILimiter.init(redis_client)

        # Salvo l'istanza Redis nello stato dell'app per utilizzarla per le WebSocket
        app.state.redis = redis_client
    except Exception as e:
        print(f"Errore di connessione a Redis: {e}")
        app.state.redis = None

@app.on_event("shutdown")
async def shutdown_event():
    """
    Evento di shutdown per chiudere la connessione a Redis.
    """
    redis_client = getattr(app.state, "redis", None)
    if redis_client:
        await redis_client.close()

@app.websocket("/{full_path:path}")
async def websocket_gateway(full_path: str, websocket: WebSocket):
    path = "/" + full_path

    # Rate limiting: blocco dell'indirizzo IP a 20 connessioni WebSocket ogni 60 secondi
    redis = getattr(app.state, "redis", None)
    client_host = websocket.client.host if websocket.client else "unknown"

    try:
        await check_ws_rate_limit(redis, key=client_host, limit=20, window=60)
    except HTTPException as e:
        raise WebSocketException(code=1013, reason=e.detail)
    
    # Accetto la connessione WebSocket
    await websocket.accept()

    # Identificazione del servizio di destinazione
    service = resolve_service(path)

    # Verifiche preliminari

    if not service or service != "notifications":
        await websocket.close(code=1008, reason="Servizio non supportato per WebSocket.")
        return
    
    if path.startswith("/internal"):
        await websocket.close(code=1008, reason="Accesso ai path interni non consentito.")
        return

    
    # Validazione parametri
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Token di autorizzazione mancante.")
        return
    
    # Validazione parametro 'field'
    field = websocket.query_params.get("field")
    if not field:
        await websocket.close(code=1008, reason="Parametro 'field' mancante.")
        return
    
    # Verifica del token JWT
    try:
        verify_jwt_token(f"Bearer {token}")
    except HTTPException as e:
        await websocket.close(code=1008, reason=e.detail)
        return

    # Costruzione dell'URL di destinazione
    base_url = SERVICE_URLS[service]
    if base_url.startswith("http://"):
        base_url = base_url.replace("http://", "ws://")
    elif base_url.startswith("https://"):
        base_url = base_url.replace("https://", "wss://")

    target_url = f"{base_url}/{full_path}"
    if websocket.query_params:
        target_url += f"?{websocket.query_params}"

    # query_string = ""
    # if websocket.query_params:
    #     query_string = f"&".join([f"{k}={v}" for k, v in websocket.query_params.items()])
    # target_url = f"{base_url}/{full_path}?{query_string}" if query_string else f"{base_url}/{full_path}"

    close_code = 1000
    close_reason = "Chiusura normale"

    print("Connessione WebSocket al servizio di destinazione:", target_url)

    try:
        async with websockets.connect(target_url) as target_ws:

            """Legge dal client e invia al backend"""
            async def forward_to_target():
                try:
                    while True:
                        data = await websocket.receive_text()
                        await target_ws.send(data)
                except WebSocketDisconnect:
                    print("Client disconnesso")
                    pass
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    print(f"Errore nella connessione al servizio di destinazione: {e}")
                    pass

            """Legge dal backend e invia al client"""
            async def forward_to_client():
                nonlocal close_code, close_reason
                try:
                    while True:
                        data = await target_ws.recv()
                        await websocket.send_text(data)
                except websockets.exceptions.ConnectionClosed as e:
                    # Il backend ha chiuso la connessione, restituisco il codice di chiusura e il motivo al client
                    print("Servizio di destinazione disconnesso")
                    close_code = e.code
                    close_reason = e.reason
                except asyncio.CancelledError:
                    pass
                except Exception:
                    print("Errore nella connessione al servizio di destinazione")
                    pass
            
            tasks = [
                asyncio.create_task(forward_to_target()),
                asyncio.create_task(forward_to_client())
            ]

            # Aspetta che almeno uno dei due task termini
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            # Cancella task pendenti per liberare risorse
            for task in pending:
                task.cancel()
    except websockets.exceptions.InvalidStatusCode as e:
        # Se il backend risponde con uno status code non valido
        print(f"Errore di connessione al servizio di destinazione: {e.status_code}")
        await websocket.close(code=1011, reason="Errore di connessione al servizio di destinazione.")
        return
    except Exception:
        print("Errore nella connessione al servizio di destinazione")
        await websocket.close(code=1011, reason="Errore nella connessione al servizio di destinazione.")
        return
    
    # Chiude la connessione WebSocket con il codice e il motivo appropriati
    try:
        await websocket.close(code=close_code, reason=close_reason)
    except Exception:
        pass

@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"], dependencies=[Depends(RateLimiter(times=100, seconds=60))])
async def gateway(full_path: str, request: Request):
    path = "/" + full_path

    # Impedisco l'accesso WebSocket tramite questo endpoint HTTP
    if path.startswith("/ws"):
        raise HTTPException(status_code=400, detail="Usa una connessione WebSocket per questo path.")

    service = resolve_service(path)

    if not service:
        raise HTTPException(status_code=404, detail="Servizio non trovato per questo path.")
    
    if path.startswith("/internal"):
        raise HTTPException(status_code=403, detail="Accesso ai path interni non consentito.")
    
    if path not in PUBLIC_PATHS:
        auth_header = request.headers.get("Authorization")
        verify_jwt_token(auth_header)
    
    return await proxy_request(
        request,
        target_base_url=SERVICE_URLS[service],
        forward_path=full_path
    )