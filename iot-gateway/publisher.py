import asyncio
import json
from aio_pika import connect_robust, Message, DeliveryMode, ExchangeType

class RabbitMQPublisher:
    def __init__(self, rabbitmq_url: str, exchange_name: str):
        self.rabbitmq_url = rabbitmq_url
        self.exchange_name = exchange_name
        self.connection = None
        self.channel = None
        self.exchange = None

    async def connect(self):
        try:
            self.connection = await connect_robust(self.rabbitmq_url, publish_confirms=True)
            self.channel = await self.connection.channel()
            self.exchange = await self.channel.declare_exchange(self.exchange_name, durable=True, type=ExchangeType.TOPIC)
        except Exception as e:
            print(f"Errore durante la connessione a RabbitMQ: {e}")

    async def publish(self, data: dict):
        if not self.channel:
            raise Exception("Il publisher non è connesso a RabbitMQ")
        try:
            routing_key = f"field.{data['field_id']}.device.{data['sensor_id']}"
            
            message_body = json.dumps(data, default=str).encode()
            message = Message(message_body,delivery_mode=DeliveryMode.PERSISTENT)
            await self.exchange.publish(message,routing_key=routing_key)
        except Exception as e:
            print(f"Errore durante la pubblicazione su RabbitMQ: {e}")
            raise e

    async def close(self):
        if self.connection:
            await self.connection.close()