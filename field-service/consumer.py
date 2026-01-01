from aio_pika import connect_robust, IncomingMessage
from database import AsyncSessionLocal
from datetime import datetime
from models import SensorReadings
import json

class RabbitMQFieldConsumer:
    def __init__(self, rabbitmq_url: str, queue_name: str):
        self.rabbitmq_url = rabbitmq_url
        self.queue_name = queue_name
        self.connection = None
        self.channel = None
        self.queue = None

    async def connect(self):
        self.connection = await connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()

        await self.channel.set_qos(prefetch_count=10)

        self.queue = await self.channel.declare_queue(self.queue_name, durable=True)
        await self.queue.consume(self.handle_message)

    async def handle_message(self, message: IncomingMessage):
        async with message.process(requeue=True):
            try:
                payload = json.loads(message.body.decode())
                payload["timestamp"] = datetime.fromisoformat(payload["timestamp"])

                print(f"Received message: {payload}")

                async with AsyncSessionLocal() as session:
                    try:
                        new_reading = SensorReadings(**payload)
                        session.add(new_reading)
                        await session.commit()
                        print(f"Inserted sensor reading into database: {new_reading}")
                    except Exception as db_error:
                        await session.rollback()
                        print(f"Database error: {db_error}")
                        raise db_error

            except Exception as e:
                print(f"Errore nel processing del messaggio: {e}")
                raise e
    
    async def close(self):
        if self.connection:
            await self.connection.close()