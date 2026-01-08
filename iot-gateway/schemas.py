from pydantic import BaseModel
from datetime import datetime

class SensorReading(BaseModel):
    """
    Modello per le rilevazioni dei sensori.
    """
    sensor_id: str
    field_id: str
    sensor_type: str
    value: float
    unit: str
    timestamp: datetime