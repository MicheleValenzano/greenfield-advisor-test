from sqlalchemy import Column, Integer, String, Date, Boolean, Double, Computed, ForeignKey, UniqueConstraint, DateTime, Index
from database import Base

class Field(Base):
    __tablename__ = 'fields'

    id = Column(Integer, primary_key=True, index=True)
    field = Column(String, Computed("('field' || id)::text", persisted=True), unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    latitude = Column(Double, nullable=False)
    longitude = Column(Double, nullable=False)
    cultivation_type = Column(String, nullable=False)
    start_date = Column(Date, nullable=True)
    size = Column(Integer, nullable=False)
    is_indoor = Column(Boolean, nullable=False)
    owner_id = Column(Integer, nullable=False)

class SensorType(Base):
    __tablename__ = 'sensor_types'

    id = Column(Integer, primary_key=True, unique=True, index=True)
    sensor = Column(String, Computed("('sensor' || id)::text", persisted=True), unique=True, index=True, nullable=False)
    type_name = Column(String, nullable=False, unique=True, index=True)
    description = Column(String, nullable=True)
    unit = Column(String, nullable=False)
    owner_id = Column(Integer, nullable=False)

class FieldSensors(Base):
    __tablename__ = 'field_sensors'

    id = Column(Integer, primary_key=True, unique=True, index=True)
    sensor_id = Column(String, nullable=False)
    sensor_type = Column(String, ForeignKey("sensor_types.type_name", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False)
    location = Column(String, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    field_name = Column(String, ForeignKey("fields.field", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    owner_id = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint('sensor_id', 'field_name', name='uix_sensor_id_field_name'),
    )

class SensorReadings(Base):
    __tablename__ = 'sensor_readings'

    id = Column(Integer, primary_key=True, unique=True, index=True)
    sensor_id = Column(String, nullable=False)
    field_id = Column(String, nullable=False)
    sensor_type = Column(String, nullable=False)
    value = Column(Double, nullable=False)
    unit = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index('idx_sensor_readings_field_type_time', 'field_id', 'sensor_type', timestamp.desc()),
    )