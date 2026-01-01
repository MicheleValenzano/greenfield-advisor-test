from pydantic import BaseModel
from datetime import datetime

class SensorReading(BaseModel):
    sensor_id: str
    field_id: str
    sensor_type: str
    value: float
    unit: str
    timestamp: datetime