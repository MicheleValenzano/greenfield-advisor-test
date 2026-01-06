from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime
import re

LOCATION_PATTERN = r"^[A-Za-zÀ-ÖØ-öø-ÿ' -]+ \((-?\d+(?:\.\d+)?), (-?\d+(?:\.\d+)?)\)$"

class FieldCreation(BaseModel):
    name: str = Field(..., example="Vigna Nord", description="Nome del campo")
    location: str = Field(..., example="Rutigliano (41.1234, 16.1234)", description="Posizione geografica del campo nel formato 'Città (latitudine, longitudine)'")
    cultivation_type: str = Field(..., example="Uva da tavola", description="Tipo di coltivazione presente nel campo")
    start_date: Optional[date] = Field(None, example="2025-12-12", description="Data di inizio della coltivazione. Se non specificata, si assume la data odierna")
    size: float = Field(..., example=2.5, description="Dimensione del campo in ettari")
    is_indoor: bool = Field(..., example=False, description="Indica se il campo è coperto (serra) o all'aperto")

    @field_validator("name")
    def validate_name(cls, value):
        if not value.strip():
            raise ValueError("Il nome del campo non può essere vuoto.")
        return value
    
    @field_validator("cultivation_type")
    def validate_cultivation_type(cls, value):
        if not value.strip():
            raise ValueError("Il tipo di coltivazione non può essere vuoto.")
        return value


    @field_validator("size")
    def validate_size(cls, value):
        if value <= 0:
            raise ValueError("La dimensione del campo deve essere un valore positivo.")
        return value
    
    @field_validator("location")
    def validate_location(cls, value):
        if not re.fullmatch(LOCATION_PATTERN, value):
            raise ValueError("La posizione geografica deve essere nel formato 'Città (latitudine, longitudine)'.")
        return value

    @field_validator("start_date")
    def validate_start_date(cls, value):
        if value and value > datetime.now().date():
            raise ValueError("La data di inizio non può essere nel futuro.")
        return value
    
    @field_validator("is_indoor")
    def validate_is_indoor(cls, value):
        if not isinstance(value, bool):
            raise ValueError("Il campo 'is_indoor' deve essere un valore booleano.")
        return value

class FieldOutput(BaseModel):
    field: str = Field(..., example="field123456", description="Identificativo univoco del campo")
    name: str = Field(..., example="Vigna Nord", description="Nome del campo")
    city: str = Field(..., example="Rutigliano", description="Posizione geografica del campo nel formato")
    latitude: float = Field(..., example=41.1234, description="Latitudine del campo")
    longitude: float = Field(..., example=16.1234, description="Longitudine del campo")
    cultivation_type: str = Field(..., example="Uva da tavola", description="Tipo di coltivazione presente nel campo")
    size: float = Field(..., example=2.5, description="Dimensione del campo in ettari")

    class Config:
        orm_mode = True

class FieldUpdate(BaseModel):
    name: Optional[str] = Field(None, example="Vigna Sud", description="Nome del campo")
    cultivation_type: Optional[str] = Field(None, example="Uva da tavola", description="Tipo di coltivazione presente nel campo")
    size: Optional[float] = Field(None, example=3.0, description="Dimensione del campo in ettari")
    is_indoor: Optional[bool] = Field(None, example=True, description="Indica se il campo è coperto (serra) o all'aperto")

    @field_validator("name")
    def validate_name(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Il nome del campo non può essere vuoto.")
        return value
    
    @field_validator("cultivation_type")
    def validate_cultivation_type(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Il tipo di coltivazione non può essere vuoto.")
        return value

    @field_validator("size")
    def validate_size(cls, value):
        if value is not None and value <= 0:
            raise ValueError("La dimensione del campo deve essere un valore positivo.")
        return value
    
    @field_validator("is_indoor")
    def validate_is_indoor(cls, value):
        if value is not None and not isinstance(value, bool):
            raise ValueError("Il campo 'is_indoor' deve essere un valore booleano.")
        return value

class SensorTypeCreation(BaseModel):
    type_name: str = Field(..., example="temperatura", description="Tipo di sensore, ad esempio 'temperatura', 'umidità', ecc...")
    description: Optional[str] = Field(None, example="Sensore per misurare la temperatura dell'aria", description="Descrizione del sensore")
    unit: str = Field(..., example="°C", description="Unità di misura del sensore, ad esempio '°C', '%', ecc...")

    class Config:
        orm_mode = True

class SensorTypeOutput(BaseModel):
    sensor: str = Field(..., example="sensor1234", description="Identificativo univoco della tipologia di sensore")
    type_name: str = Field(..., example="temperatura", description="Tipo di sensore, ad esempio 'temperatura', 'umidità', ecc...")
    description: Optional[str] = Field(None, example="Sensore per misurare la temperatura dell'aria", description="Descrizione del sensore")
    unit: str = Field(..., example="°C", description="Unità di misura del sensore, ad esempio '°C', '%', ecc...")

    class Config:
        orm_mode = True

class NewSensorInField(BaseModel):
    sensor_id: str = Field(..., example="sensor1234", description="Identificativo univoco del sensore")
    sensor_type: str = Field(..., example="temperatura", description="Tipo di sensore, ad esempio 'temperatura', 'umidità', ecc...")
    location: str = Field(..., example="Nord Est", description="Posizione del sensore all'interno del campo")
    active: bool = Field(..., example=True, description="Indica se il sensore è attivo o inattivo")

    @field_validator("sensor_id")
    def validate_sensor_id(cls, value):
        if not value.strip():
            raise ValueError("L'identificativo del sensore non può essere vuoto.")
        return value
    
    @field_validator("sensor_type")
    def validate_sensor_type(cls, value):
        if not value.strip():
            raise ValueError("Il tipo di sensore non può essere vuoto.")
        return value
    
    @field_validator("location")
    def validate_location(cls, value):
        if not value.strip():
            raise ValueError("La posizione del sensore non può essere vuota.")
        return value
    
    @field_validator("active")
    def validate_active(cls, value):
        if not isinstance(value, bool):
            raise ValueError("Il campo 'active' deve essere un valore booleano.")
        return value

    class Config:
        orm_mode = True

class SensorInFieldOutput(BaseModel):
    sensor_id: str = Field(..., example="sensor1234", description="Identificativo univoco del sensore")
    sensor_type: str = Field(..., example="temperatura", description="Tipo di sensore, ad esempio 'temperatura', 'umidità', ecc...")
    location: str = Field(..., example="Nord Est", description="Posizione del sensore all'interno del campo")

    class Config:
        orm_mode = True

class SensorReadingOutput(BaseModel):
    sensor_id: str = Field(..., example="sensor1234", description="Identificativo univoco del sensore")
    sensor_type: str = Field(..., example="temperatura", description="Tipo di sensore, ad esempio 'temperatura', 'umidità', ecc...")
    value: float = Field(..., example=23.5, description="Valore della lettura del sensore")
    unit: str = Field(..., example="°C", description="Unità di misura del sensore")
    timestamp: datetime = Field(..., example="2024-01-01 12:00:00", description="Timestamp della lettura del sensore")

    class Config:
        orm_mode = True