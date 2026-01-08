from sqlalchemy import Column, Integer, String, Date, Boolean, Double, Computed, ForeignKey, UniqueConstraint, DateTime, Index
from database import Base

class Field(Base):
    """
    Schema della tabella del database per i campi agricoli.
    Attributes:
        id (int): Identificatore univoco del campo.
        field (str): Nome univoco del campo generato automaticamente.
        name (str): Nome del campo.
        city (str): Città in cui si trova il campo.
        latitude (float): Latitudine del campo.
        longitude (float): Longitudine del campo.
        cultivation_type (str): Tipo di coltivazione del campo.
        start_date (date): Data di inizio della coltivazione.
        size (int): Dimensione del campo in ettari.
        is_indoor (bool): Indica se il campo è indoor o outdoor.
        owner_id (int): Identificatore del proprietario del campo.
    """
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
    """
    Schema della tabella del database per i tipi di sensori.
    Attributes:
        id (int): Identificatore univoco del tipo di sensore.
        sensor (str): Nome univoco del sensore generato automaticamente.
        type_name (str): Nome del tipo di sensore.
        description (str): Descrizione del tipo di sensore.
        unit (str): Unità di misura del sensore.
        owner_id (int): Identificatore del proprietario del tipo di sensore.
    """
    __tablename__ = 'sensor_types'

    id = Column(Integer, primary_key=True, unique=True, index=True)
    sensor = Column(String, Computed("('sensor' || id)::text", persisted=True), unique=True, index=True, nullable=False)
    type_name = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    unit = Column(String, nullable=False)
    owner_id = Column(Integer, nullable=False)

    # Vincolo di unicità combinato su owner_id e type_name (un proprietario non può avere due tipi di sensori con lo stesso nome)
    __table_args__ = (
        UniqueConstraint('owner_id', 'type_name', name='uix_type_name_owner_id'),
    )

class FieldSensors(Base):
    """
    Schema della tabella del database per i sensori nei campi.
    Attributes:
        id (int): Identificatore univoco del sensore nel campo.
        sensor_id (str): Identificatore del sensore.
        sensor_type_id (int): Identificatore del tipo di sensore (chiave esterna).
        sensor_type (str): Tipo di sensore.
        location (str): Posizione del sensore nel campo.
        active (bool): Indica se il sensore è attivo o meno.
        field_name (str): Nome del campo a cui il sensore appartiene (chiave esterna).
        owner_id (int): Identificatore del proprietario del sensore."""
    __tablename__ = 'field_sensors'

    id = Column(Integer, primary_key=True, unique=True, index=True)
    sensor_id = Column(String, nullable=False)
    sensor_type_id = Column(Integer, ForeignKey("sensor_types.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False) # modificata
    # sensor_type = Column(String, ForeignKey("sensor_types.type_name", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False) # modificata in quella di giu
    sensor_type = Column(String, nullable=False)
    location = Column(String, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    field_name = Column(String, ForeignKey("fields.field", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    owner_id = Column(Integer, nullable=False)

    # Vincolo di unicità combinato su sensor_id e field_name (un sensore non può essere duplicato nello stesso campo)
    __table_args__ = (
        UniqueConstraint('sensor_id', 'field_name', name='uix_sensor_id_field_name'),
    )

class SensorReadings(Base):
    """
    Schema della tabella del database per le letture dei sensori.
    Attributes:
        id (int): Identificatore univoco della lettura del sensore.
        sensor_id (str): Identificatore del sensore.
        field_id (str): Identificatore del campo.
        sensor_type (str): Tipo di sensore.
        value (float): Valore della lettura del sensore.
        unit (str): Unità di misura della lettura del sensore.
        timestamp (datetime): Timestamp della lettura del sensore.
    """
    __tablename__ = 'sensor_readings'

    id = Column(Integer, primary_key=True, unique=True, index=True)
    sensor_id = Column(String, nullable=False)
    field_id = Column(String, nullable=False)
    sensor_type = Column(String, nullable=False)
    value = Column(Double, nullable=False)
    unit = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)

    # Indice per ottimizzare le query basate su field_id, sensor_type e timestamp in ordine decrescente 
    __table_args__ = (
        Index('idx_sensor_readings_field_type_time', 'field_id', 'sensor_type', timestamp.desc()),
    )