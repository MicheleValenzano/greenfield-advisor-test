from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from websocket_manager import WebSocketManager
from consumer import RabbitMQNotificationConsumer
import os
from contextlib import asynccontextmanager
import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool
import httpx
import jwt

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbit-mq/")
SENSORS_EXCHANGE_NAME = os.getenv("RABBITMQ_SENSORS_EXCHANGE", "sensor_data.topic")
ALERTS_EXCHANGE_NAME = os.getenv("RABBITMQ_ALERTS_EXCHANGE", "alerts.topic")
FIELD_ROUTING_KEY = os.getenv("RABBITMQ_FIELD_ROUTING_KEY", "field.*.device.*")
ALERTS_ROUTING_KEY = os.getenv("RABBITMQ_ALERTS_ROUTING_KEY", "alerts.*")

FIELD_SERVICE_URL = os.getenv("FIELD_SERVICE_URL", "http://field-service:8004")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis-notifications:6379")

REDIS_MAX_CONNECTIONS = 20

consumer : RabbitMQNotificationConsumer = None
websocket_manager = WebSocketManager()
redis : aioredis.Redis = None
http_client: httpx.AsyncClient = None


CACHE_TTL_PERMISSIONS = 10 * 60 # 10 minutes

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

def decode_access_token(jwt_token: str) -> dict:
    """
    Decodifica il token JWT ricevuto dal client WebSocket.
    Restituisce il payload se valido, altrimenti chiude la connessione con WebSocketDisconnect.
    :param jwt_token: Token JWT da decodificare.
    :return: Payload del token JWT.
    """
    try:
        payload = jwt.decode(jwt_token, PUBLIC_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise WebSocketDisconnect(code=1008, reason="Token di accesso scaduto.")
    except jwt.InvalidTokenError:
        raise WebSocketDisconnect(code=1008, reason="Token di accesso non valido.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer, http_client, redis

    http_client = httpx.AsyncClient()

    pool = ConnectionPool.from_url(REDIS_URL, max_connections=REDIS_MAX_CONNECTIONS)
    redis = aioredis.Redis(decode_responses=True, connection_pool=pool)

    consumer = RabbitMQNotificationConsumer(
        rabbitmq_url=RABBITMQ_URL,
        sensors_exchange_name=SENSORS_EXCHANGE_NAME,
        alerts_exchange_name=ALERTS_EXCHANGE_NAME,
        field_routing_key=FIELD_ROUTING_KEY,
        alerts_routing_key=ALERTS_ROUTING_KEY,
        websocket_manager=websocket_manager
    )
    await consumer.connect()
    yield

    if consumer:
        await consumer.close()
    if http_client:
        await http_client.aclose()
    if redis:
        await redis.close()

app = FastAPI(title="Notification Service", lifespan=lifespan)

async def check_field_permission(field: str, user_id: str, token: str) -> bool:
    cache_key = f"permission:{user_id}:{field}"
    
    if redis:
        cached_permission = await redis.get(cache_key)
        if cached_permission is not None:
            if cached_permission == "OK":
                return True
            elif cached_permission == "FORBIDDEN":
                raise WebSocketDisconnect(code=1008, reason="Non hai i permessi per accedere a questo campo.")
            elif cached_permission == "NOT_FOUND":
                raise WebSocketDisconnect(code=1008, reason="Campo non trovato.")
    
    try:
        response = await http_client.get(f"{FIELD_SERVICE_URL}/internal/validate-field-owner", params={"field_name": field}, headers={"Authorization": f"Bearer {token}"})

        if response.status_code == 200:
            if redis:
                await redis.set(cache_key, "OK", ex=CACHE_TTL_PERMISSIONS)
            return True
        elif response.status_code == 403:
            if redis:
                await redis.set(cache_key, "FORBIDDEN", ex=CACHE_TTL_PERMISSIONS)
            raise WebSocketDisconnect(code=1008, reason="Non hai i permessi per accedere a questo campo.")
        elif response.status_code == 404:
            if redis:
                await redis.set(cache_key, "NOT_FOUND", ex=CACHE_TTL_PERMISSIONS)
            raise WebSocketDisconnect(code=1008, reason="Campo non trovato.")
        else:
            raise WebSocketDisconnect(code=1011, reason="Errore interno del server.")
    except httpx.RequestError:
        raise WebSocketDisconnect(code=1011, reason="Impossibile contattare il servizio di validazione.")
        

@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket, field: str, token: str):
    await websocket.accept()
    try:
        payload = decode_access_token(token)
        print("Payload token:", payload)
        user_id = str(payload["sub"])

        if not user_id:
            raise WebSocketDisconnect(code=1008, reason="Token non valido.")

        await check_field_permission(field, user_id, token)

    except WebSocketDisconnect as e:
        print(f"Rifiuto connessione WebSocket per field: {field}, motivo: {e.reason}")
        await websocket.close(code=e.code, reason=e.reason)
        return
    except Exception as e:
        print(f"Errore durante la connessione WebSocket per field: {field}, motivo: {str(e)}")
        await websocket.close(code=1011, reason="Errore interno del server.")
        return
    
    await websocket_manager.connect(websocket, field)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, field)
    except Exception as e:
        print(f"Errore durante la comunicazione WebSocket per field: {field}, motivo: {str(e)}")
        await websocket_manager.disconnect(websocket, field)