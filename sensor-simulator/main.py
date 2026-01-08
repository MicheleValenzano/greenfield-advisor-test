import asyncio
import json
import random
from datetime import datetime, timezone
from asyncio_mqtt import Client
import httpx

FIELD_SERVICE_URL = "http://field-service:8004"

BROKER = "mqtt-broker"
PORT = 1883

SYSTEM_STATUS_TOPIC = "system/gateway/status"

PUBLISH_INTERVAL = 60

SENSORS = {}

async def fetch_sensors():
    """
    Recupera la lista dei sensori di ogni field e di ogni owner dal Field Service.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{FIELD_SERVICE_URL}/fields/all-sensors")
        response.raise_for_status()
        return response.json()

async def fetch_sensors_retry(retries=10, delay=3):
    """
    Tenta di recuperare i sensori con un meccanismo di retry.
    """
    for i in range(retries):
        try:
            return await fetch_sensors()
        except Exception as e:
            print(f"Errore nel recupero dei sensori (tentativo {i+1}/{retries}): {e}")
            await asyncio.sleep(delay)
    raise RuntimeError("Impossibile recuperare i sensori dopo più tentativi.")

# Configurazioni per tre metriche comuni
METRIC_CONFIG = {
    "TEMPERATURE": {"unit": "celsius", "min": 15, "max": 35, "noise": 0.5},
    "HUMIDITY": {"unit": "%", "min": 30, "max": 90, "noise": 1.5},
    "SOIL MOISTURE": {"unit": "%", "min": 10, "max": 60, "noise": 1.0},
}

state = {}

def generate_value(key, cfg):
    """
    Genera un valore simulato per una metrica specifica, aggiungendo un po' di rumore.
    """
    if key not in state:
        state[key] = random.uniform(cfg["min"], cfg["max"])

    drift = random.uniform(-cfg["noise"], cfg["noise"])
    v = state[key] + drift
    v = max(cfg["min"], min(cfg["max"], v))
    state[key] = v
    return round(v, 2)

async def update_sensors_loop():
    """
    Aggiorna periodicamente la lista dei sensori.
    Raises:
        Exception: Se il recupero dei sensori fallisce.
    """
    global SENSORS
    while True:
        try:
            SENSORS = await fetch_sensors()
        except Exception as e:
            print(f"Errore nel recupero dei sensori: {e}")
        await asyncio.sleep(5) # Aggiorna ogni 5 secondi

async def publish_sensor_data(client):
    """
    Pubblica i dati simulati dei sensori sul broker MQTT.
    Args:
        client (Client): Il client MQTT.
    """
    await asyncio.sleep(10)
    while True:
        for field_id, sensor_lists in SENSORS.items():
            for sensor in sensor_lists:
                sensor_id = sensor["sensor_id"]
                metric = sensor["sensor_type"]
                unit = sensor["unit"]

                if metric in METRIC_CONFIG:
                    value = generate_value(f"{field_id}:{sensor_id}:{metric}", METRIC_CONFIG[metric])
                else:
                    value = round(random.uniform(0, 100), 2)

                payload = {
                    'sensor_type': metric,
                    'value': value,
                    'unit': unit,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }

                topic = f"sensors/{field_id}/{sensor_id}/{metric}"
                await client.publish(topic, json.dumps(payload), qos=1)
                print(f"Pubblicato sul topic {topic}: {payload}")
        await asyncio.sleep(PUBLISH_INTERVAL)

async def wait_for_broker(client):
    """
    Attende che l'IoT-Gateway sia pronto a ricevere dati.
    Args:
        client (Client): Il client MQTT.
    """
    async with client.unfiltered_messages() as messages:
        await client.subscribe(SYSTEM_STATUS_TOPIC)
        async for message in messages:
            if message.topic == SYSTEM_STATUS_TOPIC and message.payload.decode() == "ready":
                print("IoT-Gateway è pronto a ricevere dati.")
                return

async def main():
    """
    Funzione principale per avviare il simulatore di sensori.
    """
    global SENSORS
    SENSORS = await fetch_sensors_retry()
    async with Client(BROKER, PORT) as client:
        await wait_for_broker(client)
        await asyncio.gather(
            update_sensors_loop(),
            publish_sensor_data(client)
        )

if __name__ == "__main__":
    asyncio.run(main())