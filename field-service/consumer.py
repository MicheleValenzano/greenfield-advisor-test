from aio_pika import connect_robust, IncomingMessage
from database import AsyncSessionLocal
from datetime import datetime
from models import SensorReadings
import json

class RabbitMQFieldConsumer:
    """
    Consumer RabbitMQ per il servizio di field-service. Consuma messaggi dalla coda specificata,
    elabora i dati dei sensori e li inserisce nel database.
    Attributes:
        rabbitmq_url (str): URL di connessione a RabbitMQ.
        queue_name (str): Nome della coda da cui consumare i messaggi.
    """
    def __init__(self, rabbitmq_url: str, queue_name: str):
        self.rabbitmq_url = rabbitmq_url
        self.queue_name = queue_name
        self.connection = None
        self.channel = None
        self.queue = None

    async def connect(self):
        """
        Connette il consumer a RabbitMQ e inizia a consumare i messaggi dalla coda specificata.
        """
        self.connection = await connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()

        # Imposta la qualità del servizio (QoS). Limita il numero massimo di messaggi non confermati a 10 per volta.
        await self.channel.set_qos(prefetch_count=10)

        self.queue = await self.channel.declare_queue(self.queue_name, durable=True)
        await self.queue.consume(self.handle_message)

    async def handle_message(self, message: IncomingMessage):
        """
        Elabora i messaggi ricevuti dalla coda. Decodifica il payload JSON,
        converte il timestamp e inserisce i dati nel database.
        Args:
            message (IncomingMessage): Messaggio ricevuto dalla coda RabbitMQ.
        """
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
        """
        Chiude la connessione a RabbitMQ.
        """
        if self.connection:
            await self.connection.close()