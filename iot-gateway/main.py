import asyncio
from asyncio_mqtt import Client, MqttError
from publisher import RabbitMQPublisher
from schemas import SensorReading
import json
import os
from datetime import datetime, timezone

MQTT_HOST = os.getenv("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensors/+/+/+")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbit-mq/")
RABBITMQ_EXCHANGE = os.getenv("RABBITMQ_SENSORS_EXCHANGE", "sensor_data.topic")

MQTT_CLIENT_ID = "iot-gateway"

SYSTEM_STATUS_TOPIC = "system/gateway/status"

class PayloadValidationError(Exception):
    """
    Eccezione sollevata quando il payload non è valido.
    """
    pass

def validate_payload(payload: dict):
    """
    Verifica che il payload rispetti i requisiti minimi.
    Args:
        payload (dict): Il payload da validare.
    Raises:
        PayloadValidationError: Se i dati non sono validi.
    """

    # Verifica la presenza dei campi obbligatori
    required_fields = ['sensor_type', 'value', 'unit', 'timestamp']
    if not all(field in payload for field in required_fields):
        raise PayloadValidationError(f"Payload mancante di campi obbligatori. Richiesti: {required_fields}")
    
    # Verifica stringhe non vuote
    if not isinstance(payload['sensor_type'], str) or not payload['sensor_type'].strip():
        raise PayloadValidationError("Il campo 'sensor_type' deve essere una stringa non vuota.")

    if not isinstance(payload['unit'], str) or not payload['unit'].strip():
        raise PayloadValidationError("Il campo 'unit' deve essere una stringa non vuota.")
    
    # Verifica numerica del valore
    if not isinstance(payload['value'], (int, float)):
        raise PayloadValidationError("Il campo 'value' deve essere un numero.")
    
    # Verifica timestamp non vuoto
    ts = payload['timestamp']
    if not isinstance(ts, str) or not ts.strip():
        raise PayloadValidationError("Il campo 'timestamp' deve essere una stringa ISO non vuota.")
    
    # Veridfico formato ISO del timestamp
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        raise PayloadValidationError("Il campo 'timestamp' non è in formato ISO valido.")
    
    # Verifico che il timestamp includa informazioni sul fuso orario
    if dt.tzinfo is None:
        raise PayloadValidationError("Il campo 'timestamp' deve includere informazioni sul fuso orario.")
    
    # Verifico che il timestamp non sia nel futuro
    current_time = datetime.now(timezone.utc)
    if dt > current_time:
        raise PayloadValidationError("Il campo 'timestamp' non può essere nel futuro.")



def mqtt_to_sensor_reading(mqtt_topic: str, payload: bytes) -> SensorReading:
    """
    Converte un messaggio MQTT in un'istanza di SensorReading.
    Args:
        mqtt_topic (str): Il topic MQTT del messaggio.
        payload (bytes): Il payload del messaggio MQTT.
    Returns:
        SensorReading: L'istanza di SensorReading creata dal messaggio MQTT.
    Raises:
        ValueError: Se il messaggio MQTT non è valido.
    """
    try:
        parts = mqtt_topic.split('/')

        if len(parts) < 4:
            print("Topic MQTT non valido:", mqtt_topic)
            return None
        
        field_id = parts[1]
        sensor_id = parts[2]

        try:
            data = json.loads(payload.decode())
        except json.JSONDecodeError as e:
            print("Payload JSON non valido:", payload.decode())
            return None

        try:
            validate_payload(data)
        except PayloadValidationError as e:
            print(f"Payload non valido: {e}")
            return None

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

publisher = RabbitMQPublisher(RABBITMQ_URL, RABBITMQ_EXCHANGE) # Publisher per RabbitMQ

async def mqtt_loop():
    """
    Loop principale per la gestione dei messaggi MQTT.
    Invia le letture valide a RabbitMQ tramite il publisher.
    """
    async with Client(MQTT_HOST, MQTT_PORT, client_id=MQTT_CLIENT_ID, clean_session=False) as client:
        async with client.unfiltered_messages() as messages:

            await client.subscribe(MQTT_TOPIC, qos=1)

            await client.publish(SYSTEM_STATUS_TOPIC, "ready", qos=1, retain=True)
    
            async for message in messages:

                if message.topic == SYSTEM_STATUS_TOPIC:
                    continue

                if message.retain:
                    print(f"Ignorato messaggio retained sul topic {message.topic}")
                    continue

                sensor_reading = mqtt_to_sensor_reading(message.topic, message.payload)

                if sensor_reading:
                    try:
                        await publisher.publish(sensor_reading.dict())
                        print(f"Lettura pubblicata: {sensor_reading}")
                    except Exception as e:
                        print(f"Errore durante l'elaborazione del messaggio: {e}")

async def run_mqtt():
    """
    Esegue il loop MQTT con gestione di eventuali riconnessioni.
    """
    while True:
        try:
            await mqtt_loop()
        except MqttError as e:
            print(f"Errore MQTT: {e}. Riconnessione in corso...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Errore nel loop MQTT: {e}")
            await asyncio.sleep(5)

async def main():
    """
    Funzione principale per avviare il gateway IoT.
    """
    await publisher.connect()
    try:
        await run_mqtt()
    finally:
        await publisher.close()

if __name__ == "__main__":
    print(RABBITMQ_URL)
    asyncio.run(main())