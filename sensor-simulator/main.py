import asyncio
import json
import random
from datetime import datetime, timezone
from asyncio_mqtt import Client

BROKER = "mqtt-broker"
PORT = 1883

PUBLISH_INTERVAL = 50

# RECUPERARE DAL SERVIZIO FIELDS

FIELDS = {
    "field1": {
        "sensor01": ["temperature", "humidity"],
        "sensor02": ["temperature", "soil_moisture"],
    },
    "field2": {
        "sensor03": ["temperature", "humidity"],
        "sensor04": ["temperature"],
    },
}

METRIC_CONFIG = {
    "temperature": {"unit": "celsius", "min": 15, "max": 35, "noise": 0.5},
    "humidity": {"unit": "%", "min": 30, "max": 90, "noise": 1.5},
    "soil_moisture": {"unit": "%", "min": 10, "max": 60, "noise": 1.0},
}

state = {}

def generate_value(key, cfg):
    if key not in state:
        state[key] = random.uniform(cfg["min"], cfg["max"])

    drift = random.uniform(-cfg["noise"], cfg["noise"])
    v = state[key] + drift
    v = max(cfg["min"], min(cfg["max"], v))
    state[key] = v
    return round(v, 2)

async def publish_sensor_data(client):
    while True:
        for field_id, sensors in FIELDS.items():
            for sensor_id, metrics in sensors.items():
                for metric in metrics:
                    cfg = METRIC_CONFIG[metric]
                    value = generate_value(f"{field_id}:{sensor_id}:{metric}", cfg)
                    payload = {
                        'sensor_type': metric,
                        'value': value,
                        'unit': cfg['unit'],
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }

                    topic = f"sensors/{field_id}/{sensor_id}/{metric}"
                    await client.publish(topic, json.dumps(payload), qos=1, retain=True)
                    print(f"Pubblicato sul topic {topic}: {payload}")
        await asyncio.sleep(PUBLISH_INTERVAL)


async def main():
    async with Client(BROKER, PORT) as client:
        await publish_sensor_data(client)

if __name__ == "__main__":
    asyncio.run(main())