from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from websocket_manager import WebSocketManager
from consumer import RabbitMQNotificationConsumer
import os
from contextlib import asynccontextmanager

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbit-mq/")
SENSORS_EXCHANGE_NAME = os.getenv("RABBITMQ_SENSORS_EXCHANGE", "sensor_data.topic")
ALERTS_EXCHANGE_NAME = os.getenv("RABBITMQ_ALERTS_EXCHANGE", "alerts.topic")
FIELD_ROUTING_KEY = os.getenv("RABBITMQ_FIELD_ROUTING_KEY", "field.*.device.*")
ALERTS_ROUTING_KEY = os.getenv("RABBITMQ_ALERTS_ROUTING_KEY", "alerts.*")

print("RABBITMQ_URL:", RABBITMQ_URL)
print("SENSORS_EXCHANGE_NAME:", SENSORS_EXCHANGE_NAME)
print("ALERTS_EXCHANGE_NAME:", ALERTS_EXCHANGE_NAME)
print("FIELD_ROUTING_KEY:", FIELD_ROUTING_KEY)
print("ALERTS_ROUTING_KEY:", ALERTS_ROUTING_KEY)

consumer : RabbitMQNotificationConsumer = None
websocket_manager = WebSocketManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer
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

app = FastAPI(title="Notification Service", lifespan=lifespan)

@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket, field: str):

    # verifico i permessi di accesso al field (da implementare (con redis))

    await websocket_manager.connect(websocket, field)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, field)