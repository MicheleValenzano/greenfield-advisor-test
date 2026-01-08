import asyncio
import os
from consumer import RabbitMQFieldConsumer
from fastapi import FastAPI, HTTPException, Depends, status, Request, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import OAuth2PasswordBearer
from schemas import FieldCreation, FieldOutput, FieldUpdate, SensorTypeCreation, NewSensorInField, SensorInFieldOutput, SensorReadingOutput, SensorTypeOutput
from sqlalchemy import select, func
from sqlalchemy.orm import aliased
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from database import engine, Base, get_db
from models import Field, SensorType, FieldSensors, SensorReadings
import re
import jwt
import httpx
from contextlib import asynccontextmanager
from typing import List

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbit-mq:5672/")
RABBITMQ_FIELD_QUEUE = os.getenv("RABBITMQ_FIELD_QUEUE", "sensor_data.field.queue")

WEATHER_SERVICE_URL = os.getenv("WEATHER_SERVICE_URL", "http://weather-service:8002")

consumer: RabbitMQFieldConsumer = None

# Pattern regex per validare il formato della posizione "città (latitudine, longitudine)"
location_pattern = r"^\s*(.+?)\s*\(\s*([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)\s*\)\s*$"

PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "PUBLIC_KEY").replace("\\n", "\n")

ALGORITHM = "RS256"

# OAuth2 scheme per l'autenticazione. Permette di estrarre automaticamente il token JWT dalle richieste.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def decode_access_token(jwt_token: str = Depends(oauth2_scheme)):
    """
    Decodifica e valida il token di accesso JWT utilizzando la chiave pubblica.
    Args:
        jwt_token (str): Token JWT da decodificare.
    Returns:
        dict: Payload decodificato del token JWT.
    Raises:
        HTTPException: Se il token è scaduto o non valido.
    """
    try:
        payload = jwt.decode(jwt_token, PUBLIC_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token di accesso scaduto.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token di accesso non valido.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestore del ciclo di vita dell'applicazione FastAPI. Inizializza i client HTTP e il consumer RabbitMQ all'avvio,
    e li chiude alla terminazione dell'applicazione.

    Args:
        app (FastAPI): Istanza dell'applicazione FastAPI.
    """
    app.state.weather_client = httpx.AsyncClient(base_url=WEATHER_SERVICE_URL, timeout=httpx.Timeout(5.0))

    headers = {"User-Agent": "FieldService/1.0"}
    app.state.http_client = httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(5.0))
    
    global consumer
    consumer = RabbitMQFieldConsumer(rabbitmq_url=RABBITMQ_URL, queue_name=RABBITMQ_FIELD_QUEUE)
    await consumer.connect()
    print("Connesso a RabbitMQ")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await app.state.weather_client.aclose()
    await app.state.http_client.aclose()
    
    if consumer:
        await consumer.close()
        print("Connessione a RabbitMQ chiusa")

# Crea l'app FastAPI con il gestore del ciclo di vita
app = FastAPI(title="Field Service", lifespan=lifespan)

def get_weather_client(request: Request) -> httpx.AsyncClient:
    """
    Ottiene il client HTTP asincrono per il servizio meteo dall'applicazione.
    Args:
        request (Request): Oggetto della richiesta FastAPI.
    Returns:
        httpx.AsyncClient: Client HTTP asincrono per il servizio meteo.
    """
    return request.app.state.weather_client

def get_http_client(request: Request) -> httpx.AsyncClient:
    """
    Ottiene il client HTTP asincrono generico dall'applicazione.
    Args:
        request (Request): Oggetto della richiesta FastAPI.
    Returns:
        httpx.AsyncClient: Client HTTP asincrono generico.
    """
    return request.app.state.http_client

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Gestore delle eccezioni per gli errori di validazione delle richieste (errori di validazione con codice 422).
    Args:
        request (Request): Oggetto della richiesta FastAPI.
        exc (RequestValidationError): Eccezione di validazione delle richieste.
    Returns:
        JSONResponse: Risposta JSON con i dettagli degli errori di validazione.
    """
    errors = exc.errors()
    formatted_errors = []
    for error in errors:
        field = error.get("loc")[-1]
        message = error.get("msg").replace("Value error, ", "")

        formatted_errors.append({"field": field, "message": message})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"errors": formatted_errors},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Gestore delle eccezioni generiche per errori interni del server.
    Args:
        request (Request): Oggetto della richiesta FastAPI.
        exc (Exception): Eccezione generica sollevata.
    Returns:
        JSONResponse: Risposta JSON con il messaggio di errore interno del server.
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "Errore interno del server."},
    )

@app.get("/fields/health", status_code=200)
async def health_check():
    return {"status": "ok"}

@app.post("/fields", response_model=FieldOutput, status_code=201)
async def create_field(field: FieldCreation, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Crea un nuovo campo agricolo associato all'utente autenticato.
    Args:
        field (FieldCreation): Dati del campo da creare.
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        FieldOutput: Dati del campo creato.
    Raises:
        HTTPException: Se il formato della posizione è invalido o si verifica un errore durante la creazione.
    """
    match = re.match(location_pattern, field.location)

    if not match:
        raise HTTPException(status_code=400, detail="Il formato della posizione è invalido. Usa 'città (latitudine, longitudine)'.")
    
    city = match.group(1)
    latitude = float(match.group(2))
    longitude = float(match.group(3))

    new_field = Field(
        name=field.name,
        city=city,
        latitude=latitude,
        longitude=longitude,
        cultivation_type=field.cultivation_type,
        start_date=field.start_date,
        size=field.size,
        is_indoor=field.is_indoor,
        owner_id=token["sub"]
    )

    db.add(new_field)
    
    try:
        await db.commit()
        await db.refresh(new_field)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Errore durante la creazione del campo.")
    
    return new_field

@app.delete("/fields/{field_name}", status_code=200)
async def delete_field(field_name: str, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Elimina un campo agricolo esistente associato all'utente autenticato.
    Args:
        field_name (str): Nome del campo da eliminare.
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        dict: Messaggio di conferma dell'eliminazione del campo.
    Raises:
        HTTPException: Se il campo non viene trovato, l'utente non ha i permessi o si verifica un errore durante l'eliminazione.
    """
    result = await db.execute(select(Field).where(Field.field == field_name))
    field = result.scalars().first()
    if not field:
        raise HTTPException(status_code=404, detail="Campo non trovato.")
    
    if field.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per eliminare questo campo.")
    
    try:
        await db.delete(field)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Errore durante l'eliminazione del campo.")
    
    return {"message": "Campo eliminato con successo."}

@app.get("/fields/{field_name}/weather")
async def get_field_weather(field_name: str, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token), weather_client: httpx.AsyncClient = Depends(get_weather_client), jwt_token: str = Depends(oauth2_scheme)):
    """
    Ottiene le informazioni meteo correnti e la previsioni meteo per un campo specifico.
    Args:
        field_name (str): Nome del campo di cui ottenere le informazioni meteo.
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
        weather_client (httpx.AsyncClient): Client HTTP asincrono per il servizio meteo.
        jwt_token (str): Token JWT dell'utente autenticato.
    Returns:
        dict: Informazioni meteo correnti e previsioni meteo per il campo specificato.
    Raises:
        HTTPException: Se il campo non viene trovato, l'utente non ha i permessi o si verificano errori di comunicazione con il servizio meteo.
    """
    result = await db.execute(select(Field).where(Field.field == field_name))
    field = result.scalars().first()
    if not field:
        raise HTTPException(status_code=404, detail="Campo non trovato.")
    
    if field.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per visualizzare le informazioni meteo di questo campo.")

    headers = {"Authorization": f"Bearer {jwt_token}"}
    params = {"lat": field.latitude, "lon": field.longitude}

    async def fetch_current():
        try:
            resp = await weather_client.get("/weather/current", params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Timeout nel servizio meteo (current).")
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Servizio meteo non disponibile (current).")
        except Exception:
            raise HTTPException(status_code=500, detail="Errore interno nel servizio meteo (current).")
    
    async def fetch_forecast():
        try:
            resp = await weather_client.get("/weather/forecast", params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Timeout nel servizio meteo (forecast).")
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Servizio meteo non disponibile (forecast).")
        except Exception:
            raise HTTPException(status_code=500, detail="Errore interno nel servizio meteo (forecast).")

    # Eseguo le due richieste in parallelo grazie alla programmazione asincrona
    current_weather, forecast = await asyncio.gather(fetch_current(), fetch_forecast())    

    return {
        "field": field_name,
        "current_weather": current_weather,
        "forecast": forecast
    }

@app.put("/fields/{field_name}", response_model=FieldOutput)
async def update_field(field_name: str, field_update: FieldUpdate, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Aggiorna le informazioni di un campo esistente associato all'utente autenticato.
    Args:
        field_name (str): Nome del campo da aggiornare.
        field_update (FieldUpdate): Dati aggiornati del campo.
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        FieldOutput: Dati del campo aggiornato.
    Raises:
        HTTPException: Se il campo non viene trovato o l'utente non ha i permessi.
    """
    result = await db.execute(select(Field).where(Field.field == field_name))
    field = result.scalars().first()
    if not field:
        raise HTTPException(status_code=404, detail="Campo non trovato.")
    
    if field.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per aggiornare questo campo.")
    
    if field_update.name is not None: field.name = field_update.name
    if field_update.cultivation_type is not None: field.cultivation_type = field_update.cultivation_type
    if field_update.size is not None: field.size = field_update.size
    if field_update.is_indoor is not None: field.is_indoor = field_update.is_indoor

    try:
        await db.commit()
        await db.refresh(field)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Errore durante l'aggiornamento del campo.")

    return field

@app.get("/fields", response_model=list[FieldOutput])
async def get_all_fields(db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Recupera tutti i campi associati all'utente autenticato.
    Args:
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        list[FieldOutput]: Lista di campi associati all'utente.
    Raises:
        HTTPException: Se si verifica un errore durante il recupero dei campi.
    """
    result = await db.execute(select(Field).where(Field.owner_id == token["sub"]))
    fields = result.scalars().all()
    return [f for f in fields]

@app.post("/sensor-types", status_code=201, response_model=SensorTypeCreation)
async def create_sensor_type(sensor_type: SensorTypeCreation, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Crea un nuovo tipo di sensore associato all'utente autenticato.
    Args:
        sensor_type (SensorTypeCreation): Dati del tipo di sensore da creare.
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        SensorTypeCreation: Dati del tipo di sensore creato.
    Raises:
        HTTPException: Se il tipo di sensore esiste già o si verifica un errore durante la creazione.
    """
    result = await db.execute(select(SensorType).where(SensorType.type_name == sensor_type.type_name, SensorType.owner_id == token["sub"]))
    existing_type = result.scalars().first()
    if existing_type:
        raise HTTPException(status_code=400, detail="Il tipo di sensore esiste già.")

    new_sensor_type = SensorType(
        type_name=sensor_type.type_name,
        description=sensor_type.description,
        unit=sensor_type.unit,
        owner_id=token["sub"]
    )

    db.add(new_sensor_type)
    try:
        await db.commit()
        await db.refresh(new_sensor_type)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Errore durante la creazione del tipo di sensore.")

    return new_sensor_type

@app.delete("/sensor-types/{sensor_name}", status_code=200)
async def delete_sensor_type(sensor_name: str, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Elimina un tipo di sensore esistente associato all'utente autenticato.
    Args:
        sensor_name (str): Nome del tipo di sensore da eliminare.
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        dict: Messaggio di conferma dell'eliminazione del tipo di sensore.
    Raises:
        HTTPException: Se il tipo di sensore non viene trovato, l'utente non ha i permessi o si verifica un errore durante l'eliminazione.
    """
    result = await db.execute(select(SensorType).where(SensorType.sensor == sensor_name))
    sensor_type = result.scalars().first()
    if not sensor_type:
        raise HTTPException(status_code=404, detail="Tipo di sensore non trovato.")
    
    if sensor_type.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per eliminare questo tipo di sensore.")
    
    try:
        await db.delete(sensor_type)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Impossibile eliminare il tipo di sensore perché è associato a dei sensori nei campi.")
    
    return {"message": "Tipo di sensore eliminato con successo."}

@app.get("/sensor-types", response_model=list[SensorTypeOutput])
async def get_sensor_types(db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Recupera tutti i tipi di sensori associati all'utente autenticato.
    Args:
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        list[SensorTypeOutput]: Lista di tipi di sensori associati all'utente.
    Raises:
        HTTPException: Se si verifica un errore durante il recupero dei tipi di sensori"""
    result = await db.execute(select(SensorType).where(SensorType.owner_id == token["sub"]))
    sensor_types = result.scalars().all()
    return [s for s in sensor_types]

@app.get("/fields/{field_name}/sensors", response_model=list[SensorInFieldOutput])
async def get_sensors_in_field(field_name: str, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Recupera tutti i sensori associati a un campo specifico dell'utente autenticato.
    Args:
        field_name (str): Nome del campo di cui recuperare i sensori.
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        list[SensorInFieldOutput]: Lista di sensori associati al campo specificato.
    Raises:
        HTTPException: Se il campo non viene trovato o l'utente non ha i permessi per visualizzarlo.
    """
    result = await db.execute(select(Field).where(Field.field == field_name))
    field = result.scalars().first()
    if not field:
        raise HTTPException(status_code=404, detail="Campo non trovato.")
    
    if field.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per visualizzare i sensori di questo campo.")
    
    result = await db.execute(select(FieldSensors).where(FieldSensors.field_name == field_name, FieldSensors.owner_id == token["sub"]))
    sensors = result.scalars().all()
    return [s for s in sensors]

@app.post("/fields/{field_name}/sensors", status_code=201, response_model=SensorInFieldOutput)
async def add_sensor_to_field(field_name: str, sensor: NewSensorInField, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Aggiunge un nuovo sensore a un campo specifico dell'utente autenticato.
    Args:
        field_name (str): Nome del campo a cui aggiungere il sensore.
        sensor (NewSensorInField): Dati del sensore da aggiungere.
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        SensorInFieldOutput: Dati del sensore aggiunto al campo.
    Raises:
        HTTPException: Se il campo o il tipo di sensore non vengono trovati, l'utente non ha i permessi, viene inserito un sensore duplicato (con lo stesso ID) o si verifica un errore durante l'aggiunta del sensore.
    """
    result = await db.execute(select(Field).where(Field.field == field_name))
    field = result.scalars().first()
    if not field:
        raise HTTPException(status_code=404, detail="Campo non trovato.")
    
    if field.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per aggiungere un sensore a questo campo.")
    
    result = await db.execute(select(SensorType).where(SensorType.type_name == sensor.sensor_type, SensorType.owner_id == token["sub"]))
    sensor_type = result.scalars().first()
    if not sensor_type:
        raise HTTPException(status_code=404, detail="Tipo di sensore non trovato.")

    result = await db.execute(select(FieldSensors).where(FieldSensors.sensor_id == sensor.sensor_id, FieldSensors.field_name == field_name, FieldSensors.owner_id == token["sub"]))
    existing_sensor = result.scalars().first()
    if existing_sensor:
        raise HTTPException(status_code=400, detail="Un sensore con questo ID esiste già in questo campo.")

    new_sensor = FieldSensors(
        sensor_id=sensor.sensor_id,
        sensor_type=sensor.sensor_type,
        sensor_type_id=sensor_type.id,  # modificata
        location=sensor.location,
        active=sensor.active,
        field_name=field_name,
        owner_id=token["sub"]
    )

    db.add(new_sensor)
    try:
        await db.commit()
        await db.refresh(new_sensor)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Errore durante l'aggiunta del sensore al campo.")
    
    return new_sensor

@app.delete("/fields/{field_name}/sensors/{sensor_id}", status_code=200)
async def delete_sensor_from_field(field_name: str, sensor_id: str, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Elimina un sensore da un campo specifico dell'utente autenticato.
    Args:
        field_name (str): Nome del campo da cui eliminare il sensore.
        sensor_id (str): ID del sensore da eliminare.
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        dict: Messaggio di conferma dell'eliminazione del sensore dal campo.
    Raises:
        HTTPException: Se il campo o il sensore non vengono trovati, l'utente non ha i permessi o si verifica un errore durante l'eliminazione del sensore.
    """
    # trovo la field
    result = await db.execute(select(Field).where(Field.field == field_name))
    field = result.scalars().first()
    if not field:
        raise HTTPException(status_code=404, detail="Campo non trovato.")
    
    if field.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per eliminare un sensore da questo campo.")

    result = await db.execute(select(FieldSensors).where(FieldSensors.sensor_id == sensor_id, FieldSensors.field_name == field_name))
    sensor = result.scalars().first()
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensore non trovato in questo campo.")
    
    if sensor.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per eliminare questo sensore da questo campo.")
    
    try:
        await db.delete(sensor)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Errore durante l'eliminazione del sensore dal campo.")
    
    return {"message": "Sensore eliminato con successo dal campo."}

@app.get("/fields/{field_name}/readings", response_model=list[SensorReadingOutput])
async def get_field_sensor_readings(field_name: str, limit: int = 10, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Ottiene le ultime rilevazioni dei sensori per un campo specifico dell'utente autenticato.
    Args:
        field_name (str): Nome del campo di cui ottenere le rilevazioni dei sensori.
        limit (int): Numero massimo di rilevazioni da restituire (default: 10).
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        list[SensorReadingOutput]: Lista delle ultime rilevazioni dei sensori per il campo specificato.
    Raises:
        HTTPException: Se il campo non viene trovato o l'utente non ha i permessi per visualizzarlo.
    """
    result = await db.execute(select(Field).where(Field.field == field_name))
    field = result.scalars().first()
    if not field:
        raise HTTPException(status_code=404, detail="Campo non trovato.")
    
    if field.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per visualizzare le letture dei sensori di questo campo.")
    
    result = await db.execute(
        select(SensorReadings)
        .where(SensorReadings.field_id == field_name)
        .order_by(SensorReadings.timestamp.desc())
        .limit(limit)
    )
    readings = result.scalars().all()
    return [r for r in readings]

# Ottengo tutte le rilevazioni raggruppate per tipo di sensore
@app.get("/fields/{field_name}/latest-types-readings")
async def get_last_readings_by_sensor_type(field_name: str, limit: int = 50, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Ottiene le ultime rilevazioni dei sensori raggruppate per tipo di sensore per un campo specifico dell'utente autenticato.
    Args:
        field_name (str): Nome del campo di cui ottenere le rilevazioni dei sensori.
        limit (int): Numero massimo di rilevazioni per tipo di sensore da restituire (default: 50).
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        dict: Rilevazioni dei sensori raggruppate per tipo di sensore per il campo specificato.
    Raises:
        HTTPException: Se il campo non viene trovato o l'utente non ha i permessi per visualizzarlo.
    """
    result = await db.execute(select(Field).where(Field.field == field_name))
    field_obj = result.scalars().first()
    if not field_obj:
        raise HTTPException(status_code=404, detail="Campo non trovato.")
    
    if field_obj.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per visualizzare le letture dei sensori di questo campo.")
    
    stmt = (
        select(
            SensorReadings,
            func.row_number()
            .over(
                partition_by=SensorReadings.sensor_type,
                order_by=SensorReadings.timestamp.desc()
            )
            .label("rn")
        )
        .where(SensorReadings.field_id == field_name)
    ).subquery()

    sr = aliased(SensorReadings, stmt)

    query = (
        select(sr)
        .where(stmt.c.rn <= limit)
        .order_by(sr.sensor_type, sr.timestamp.desc())
    )

    result = await db.execute(query)
    rows = result.scalars().all()

    grouped_readings = defaultdict(list)
    for row in rows:
        grouped_readings[row.sensor_type].append({
            "sensor_id": row.sensor_id,
            "field_id": row.field_id,
            "value": row.value,
            "unit": row.unit,
            "timestamp": row.timestamp
        })

    return grouped_readings

@app.put("/fields/{field_name}/sensors/{sensor_id}/change_state", status_code=200)
async def activate_deactivate_sensor(field_name: str, sensor_id: str, active: bool, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Attiva o disattiva un sensore in un campo specifico dell'utente autenticato.
    Args:
        field_name (str): Nome del campo in cui si trova il sensore.
        sensor_id (str): ID del sensore da attivare o disattivare.
        active (bool): Stato da impostare (True per attivare, False per disattivare).
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        dict: Messaggio di conferma dell'attivazione o disattivazione del sensore.
    Raises:
        HTTPException: Se il campo o il sensore non vengono trovati, l'utente non ha i permessi o si verifica un errore durante l'aggiornamento dello stato del sensore.
    """
    result = await db.execute(select(Field).where(Field.field == field_name))
    field = result.scalars().first()
    if not field:
        raise HTTPException(status_code=404, detail="Campo non trovato.")
    
    if field.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per modificare lo stato del sensore in questo campo.")

    result = await db.execute(select(FieldSensors).where(FieldSensors.sensor_id == sensor_id, FieldSensors.field_name == field_name))
    sensor = result.scalars().first()
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensore non trovato in questo campo.")
    
    if sensor.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per modificare lo stato di questo sensore in questo campo.")
    
    sensor.active = active

    try:
        await db.commit()
        await db.refresh(sensor)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Errore durante l'aggiornamento dello stato del sensore.")
    
    return {"message": f"Sensore {'attivato' if active else 'disattivato'} con successo."}

@app.get("/internal/validate-rule")
async def validate_rule_internal(field: str, sensor_type: str, user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Verifica se una regola può essere applicata a un campo specifico per un utente specifico.
    Args:
        field (str): Nome del campo.
        sensor_type (str): Tipo di sensore.
        user_id (int): ID dell'utente.
        db (AsyncSession): Sessione asincrona del database.
    Returns:
        dict: Messaggio di conferma della validità della regola.
    Raises:
        HTTPException: Se il campo o il tipo di sensore non vengono trovati o l'utente non ha i permessi.
    """
    
    result = await db.execute(select(Field).where(Field.field == field))
    field = result.scalars().first()
    if not field:
        raise HTTPException(status_code=404, detail="Campo non trovato.")
    
    if field.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Non hai i permessi per aggiungere regole in questo campo.")
    
    result = await db.execute(select(SensorType).where(SensorType.type_name == sensor_type, SensorType.owner_id == user_id))
    sensor_type_obj = result.scalars().first()
    if not sensor_type_obj:
        raise HTTPException(status_code=404, detail="Tipo di sensore non trovato.")

    return {"message": "Regola valida."}

@app.get("/fields/{field_name}/specific-types-readings")
async def get_specific_types_readings(field_name: str, sensor_types: List[str] = Query(...), limit: int = 50, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Ottiene le ultime rilevazioni dei sensori per tipi di sensori specifici in un campo specifico dell'utente autenticato.
    Args:
        field_name (str): Nome del campo di cui ottenere le rilevazioni dei sensori.
        sensor_types (List[str]): Lista di tipi di sensori di cui ottenere le rilevazioni.
        limit (int): Numero massimo di rilevazioni per tipo di sensore da restituire (default: 50).
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        dict: Rilevazioni dei sensori per i tipi di sensori specificati per il campo specificato.
    Raises:
        HTTPException: Se il campo non viene trovato o l'utente non ha i permessi per visualizzarlo.
    """
    result = await db.execute(select(Field).where(Field.field == field_name))
    field = result.scalars().first()
    if not field:
        raise HTTPException(status_code=404, detail="Campo non trovato.")
    
    if field.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per visualizzare le letture dei sensori di questo campo.")
    
    stmt = (
        select(
            SensorReadings,
            func.row_number()
            .over(
                partition_by=SensorReadings.sensor_type,
                order_by=SensorReadings.timestamp.desc()
            )
            .label("rn")
        )
        .where(
            SensorReadings.field_id == field_name,
            SensorReadings.sensor_type.in_(sensor_types)
        )
    ).subquery()

    sr = aliased(SensorReadings, stmt)

    query = (
        select(sr)
        .where(stmt.c.rn <= limit)
        .order_by(sr.sensor_type, sr.timestamp.desc())
    )

    result = await db.execute(query)
    rows = result.scalars().all()

    grouped_readings = defaultdict(list)

    for row in rows:
        grouped_readings[row.sensor_type].append({
            "sensor_id": row.sensor_id,
            "field_id": row.field_id,
            "value": row.value,
            "unit": row.unit,
            "timestamp": row.timestamp
        })
    
    ordered_grouped_readings = {}
    for sensor_type in sensor_types:
        if sensor_type in grouped_readings:
            ordered_grouped_readings[sensor_type] = grouped_readings[sensor_type]
        else:
            ordered_grouped_readings[sensor_type] = []

    return ordered_grouped_readings

@app.get("/internal/validate-field-owner")
async def validate_field_owner_internal(field_name: str, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    """
    Verifica se l'utente autenticato è il proprietario di un campo specifico.
    Args:
        field_name (str): Nome del campo.
        db (AsyncSession): Sessione asincrona del database.
        token (dict): payload del token JWT decodificato dell'utente autenticato.
    Returns:
        dict: Messaggio di conferma della proprietà del campo.
    Raises:
        HTTPException: Se il campo non viene trovato o l'utente non è il proprietario del campo.
    """
    result = await db.execute(select(Field).where(Field.field == field_name))
    field_object = result.scalars().first()
    if not field_object:
        raise HTTPException(status_code=404, detail="Campo non trovato.")
    
    if field_object.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per accedere a questo campo.")

    return {"message": "Proprietario del campo validato."}

@app.get("/fields/geocoding/reverse")
async def reverse_geocoding(lat: float, lon: float, http_client: httpx.AsyncClient = Depends(get_http_client), token: dict = Depends(decode_access_token)):
    """
    Proxy verso il servizio di geocoding inverso di OpenStreetMap Nominatim.
    Restituisce la città corrispondente alle coordinate fornite.
    Parametri:
    - lat: latitudine
    - lon: longitudine
    Returns:
    - JSON con i dettagli della località.
    Raises:
    - HTTPException in caso di errori nel servizio di geocoding inverso.
    """

    url = "https://nominatim.openstreetmap.org/reverse"
    params = {"lat": lat, "lon": lon, "format": "json"}
    try:
        response = await http_client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout nel servizio di geocoding inverso.")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Servizio di geocoding inverso non disponibile.")
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=500, detail="Errore nel servizio di geocoding inverso.")

@app.get("/fields/geocoding/search")
async def search_geocoding(name: str, count: int = 5, http_client: httpx.AsyncClient = Depends(get_http_client), token: dict = Depends(decode_access_token)):
    """
    Proxy verso il servizio di geocoding di Open-Meteo per la ricerca della città.
    Restituisce una lista di località corrispondenti al nome fornito.
    Parametri:
    - name: nome della località da cercare
    - count: numero massimo di risultati da restituire
    Returns:
    - JSON con la lista delle località trovate.
    Raises:
    - HTTPException in caso di errori nel servizio di geocoding.
    """

    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": name, "count": count, "language": "it", "format": "json"}

    try:
        response = await http_client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout nel servizio di geocoding.")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Servizio di geocoding non disponibile.")
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=500, detail="Errore nel servizio di geocoding.")

@app.get("/fields/all-sensors")
async def get_all_sensors_public(db: AsyncSession = Depends(get_db)):
    """
    Recupera tutti i sensori di tutti i campi (endpoint pubblico per la generazione dei dati).
    Returns:
        lista dei sensori di tutti i campi, raggruppati per campo.
    Raises:
        HTTPException: Se si verifica un errore durante il recupero dei sensori.
    """
    
    stmt = (
        select(
            FieldSensors.field_name,
            FieldSensors.sensor_id,
            FieldSensors.sensor_type,
            SensorType.unit
        )
        .join(SensorType,
              SensorType.id == FieldSensors.sensor_type_id
        )
        .where(FieldSensors.active == True)
    )

    result = await db.execute(stmt)
    rows = result.all()

    sensors_by_field = defaultdict(list)

    for field_name, sensor_id, sensor_type, unit in rows:
        sensors_by_field[field_name].append({
            "sensor_id": sensor_id,
            "sensor_type": sensor_type,
            "unit": unit
        })
    
    return sensors_by_field