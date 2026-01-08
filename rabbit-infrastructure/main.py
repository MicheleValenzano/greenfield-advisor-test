import asyncio
import os
from aio_pika import connect_robust, ExchangeType

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")

RABBITMQ_SENSORS_EXCHANGE = os.getenv("RABBITMQ_SENSORS_EXCHANGE", "sensor_data.topic")
RABBITMQ_ALERTS_EXCHANGE = os.getenv("RABBITMQ_ALERTS_EXCHANGE", "alerts.topic")

RABBITMQ_FIELD_QUEUE = os.getenv("RABBITMQ_FIELD_QUEUE", "sensor_data.field.queue")
RABBITMQ_INTELLIGENT_QUEUE = os.getenv("RABBITMQ_INTELLIGENT_QUEUE", "sensor_data.intelligent.queue")

RABBITMQ_FIELD_ROUTING_KEY = os.getenv("RABBITMQ_FIELD_ROUTING_KEY", "field.*.device.*")

async def setup():
    """
    Configura l'infrastruttura RabbitMQ creando exchanges, code e binding necessari.
    Questo script deve essere eseguito una sola volta per impostare l'infrastruttura.
    è utile per creare l'infrastruttura prima di avviare i servizi che la utilizzeranno, in modo che i messaggi non vadano persi.
    """
    conn = await connect_robust(RABBITMQ_URL)
    channel = await conn.channel()

    # Dichiarazione exchanges (sensori e alert)
    sensors_exchange = await channel.declare_exchange(RABBITMQ_SENSORS_EXCHANGE, ExchangeType.TOPIC, durable=True)
    alerts_exchange = await channel.declare_exchange(RABBITMQ_ALERTS_EXCHANGE, ExchangeType.TOPIC, durable=True)

    # Dichiarazione code (field, intelligent, notifications, alerts)
    field_queue = await channel.declare_queue(RABBITMQ_FIELD_QUEUE, durable=True)
    intelligent_queue = await channel.declare_queue(RABBITMQ_INTELLIGENT_QUEUE, durable=True)

    # Binding code agli exchange con le routing key appropriate
    await field_queue.bind(sensors_exchange, routing_key=RABBITMQ_FIELD_ROUTING_KEY)
    await intelligent_queue.bind(sensors_exchange, routing_key=RABBITMQ_FIELD_ROUTING_KEY)

    print("Infrstruttura RabbitMQ configurata con successo.")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(setup())