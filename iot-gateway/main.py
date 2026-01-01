import asyncio
from asyncio_mqtt import Client
from publisher import RabbitMQPublisher
from schemas import SensorReading
import json
import os

MQTT_HOST = os.getenv("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensors/+/+/+")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbit-mq/")
RABBITMQ_EXCHANGE = os.getenv("RABBITMQ_SENSORS_EXCHANGE", "sensor_data.topic")

def mqtt_to_sensor_reading(mqtt_topic: str, payload: bytes) -> SensorReading:
    try:
        parts = mqtt_topic.split('/')

        if len(parts) < 4:
            raise ValueError("Formato del topic MQTT non valido")
        
        field_id = parts[1]
        sensor_id = parts[2]

        data = json.loads(payload.decode())

        return SensorReading(
            sensor_id=sensor_id,
            field_id=field_id,
            sensor_type=data['sensor_type'],
            value=data['value'],
            unit=data['unit'],
            timestamp=data['timestamp']
        )
    except Exception as e:
        raise ValueError(f"Errore durante la conversione del messaggio MQTT: {e}")

publisher = RabbitMQPublisher(RABBITMQ_URL, RABBITMQ_EXCHANGE)

async def mqtt_loop():
    async with Client(MQTT_HOST, MQTT_PORT) as client:
        async with client.unfiltered_messages() as messages:
            await client.subscribe(MQTT_TOPIC)
    
            async for message in messages:
                try:
                    sensor_reading = mqtt_to_sensor_reading(message.topic, message.payload)
                    await publisher.publish(sensor_reading.dict())
                    print(f"Lettura pubblicata: {sensor_reading}")
                except Exception as e:
                    print(f"Errore durante l'elaborazione del messaggio: {e}")

async def run_mqtt():
    while True:
        try:
            await mqtt_loop()
        except Exception as e:
            print(f"Errore nel loop MQTT: {e}")
            await asyncio.sleep(5)

async def main():
    await publisher.connect()
    try:
        await run_mqtt()
    finally:
        await publisher.close()

if __name__ == "__main__":
    print(RABBITMQ_URL)
    asyncio.run(main())