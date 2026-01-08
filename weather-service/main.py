import os
import json
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
import httpx
import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool
from pydantic import BaseModel, Field
from dateutil import parser
from collections import defaultdict
import jwt

app = FastAPI(title="Weather Service")

# Definizione di OAuth2PasswordBearer per ottenere il token JWT negli endpoint automaticamente
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis-weather:6379")
REDIS_MAX_CONNECTIONS = 20

OPENWEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "API_KEY")
BASE_OPENWEATHER_URL = "http://api.openweathermap.org/data/2.5"

CACHE_TTL_CURRENT_WEATHER = 5 * 60 # Tempo di vita della cache per il meteo attuale: 5 minuti
CACHE_TTL_FORECAST = 6 * 60 * 60  # Tempo di vita della cache per le previsioni meteo: 6 ore (poiché cambiano meno frequentemente)

# Connessione Redis globale, utilizzata per il caching dei dati meteo (meteo attuale e previsioni)
redis: aioredis.Redis = None

PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "PUBLIC_KEY").replace("\\n", "\n")

ALGORITHM = "RS256"

def decode_access_token(jwt_token: str = Depends(oauth2_scheme)):
    """
    Decodifica e verifica il token di accesso JWT.
    Args:
        jwt_token (str): Il token JWT da decodificare.
    Returns:
        dict: Il payload decodificato del token JWT.
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

@app.on_event("startup")
async def startup_event():
    """
    Inizializza la connessione a Redis all'avvio dell'applicazione.
    """
    global redis
    pool = ConnectionPool.from_url(REDIS_URL, max_connections=REDIS_MAX_CONNECTIONS)
    redis = aioredis.Redis(decode_responses=True, connection_pool=pool)

@app.on_event("shutdown")
async def shutdown_event():
    """
    Chiude la connessione a Redis alla chiusura dell'applicazione.
    """
    global redis
    if redis:
        await redis.close()

class CurrentWeatherResponse(BaseModel):
    """
    Modello di risposta per il meteo attuale.
    """
    city: str = Field(..., description="Nome della città", example="Roma")
    temperature: float = Field(..., description="Temperatura attuale in gradi Celsius", example=22.5)
    min_temperature: int = Field(..., description="Temperatura minima in gradi Celsius", example=18)
    max_temperature: int = Field(..., description="Temperatura massima in gradi Celsius", example=27)
    description: str = Field(..., description="Descrizione delle condizioni metereologiche", example="Sereno")
    icon: str = Field(..., description="Codice icona rappresentativa delle condizioni meteo", example="01d")

class DailyForecastResponse(BaseModel):
    """
    Modello di risposta per le previsioni meteo giornaliere.
    """
    date: str = Field(..., description="Data della previsione", example="20 Dec")
    min_temperature: int = Field(..., description="Temperatura minima in gradi Celsius", example=8)
    max_temperature: int = Field(..., description="Temperatura massima in gradi Celsius", example=14)
    icon: str = Field(..., description="Codice icona rappresentativa delle condizioni meteo", example="01d")

@app.get("/weather/current", response_model=CurrentWeatherResponse)
async def get_current_weather(lat: float, lon: float, token: dict = Depends(decode_access_token)):
    """
    Recupera il meteo attuale per una data posizione geografica (latitudine e longitudine).
    Utilizza il caching con Redis per migliorare le prestazioni.
    Args:
        lat (float): Latitudine della posizione.
        lon (float): Longitudine della posizione.
        token (dict): Payload del token JWT decodificato.
    Returns:
        CurrentWeatherResponse: Dati meteo attuali.
    Raises:
        HTTPException: Se il servizio meteo non è disponibile o si verifica un errore.
    """
    if not redis:
        print("Servizio Redis non disponibile.")
    
    rounded_lat = round(lat, 4)
    rounded_lon = round(lon, 4)
    cache_key = f"weather:current:{rounded_lat}:{rounded_lon}"

    try:
        cached_data = await redis.get(cache_key)
    except Exception:
        cached_data = None

    if cached_data:
        return CurrentWeatherResponse(**json.loads(cached_data))
    
    params = {
        "lat": lat,
        "lon": lon,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "it"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_OPENWEATHER_URL}/weather", params=params)
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Servizio meteo non disponibile.")
    

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Errore nel recupero dei dati meteo attuali.")
    
    data = response.json()

    weather = CurrentWeatherResponse(
        city=data["name"],
        temperature=data["main"]["temp"],
        min_temperature=round(data["main"]["temp_min"]),
        max_temperature=round(data["main"]["temp_max"]),
        description=data["weather"][0]["description"],
        icon=data["weather"][0]["icon"]
    )

    if redis:
        await redis.set(cache_key, weather.json(), ex=CACHE_TTL_CURRENT_WEATHER)
    
    return weather

@app.get("/weather/forecast", response_model=list[DailyForecastResponse])
async def get_weather_forecast(lat: float, lon: float, token: dict = Depends(decode_access_token)):
    """
    Recupera le previsioni meteo giornaliere per una data posizione geografica (latitudine e longitudine).
    Utilizza il caching con Redis per migliorare le prestazioni.
    Args:
        lat (float): Latitudine della posizione.
        lon (float): Longitudine della posizione.
        token (dict): Payload del token JWT decodificato.
    Returns:
        list[DailyForecastResponse]: Elenco delle previsioni meteo giornaliere.
    Raises:
        HTTPException: Se il servizio meteo non è disponibile o si verifica un errore.
    """
    if not redis:
        print("Servizio Redis non disponibile.")
    
    rounded_lat = round(lat, 4)
    rounded_lon = round(lon, 4)
    cache_key = f"weather:forecast:{rounded_lat}:{rounded_lon}"

    try:
        cached_data = await redis.get(cache_key)
    except Exception:
        cached_data = None

    if cached_data:
        return [DailyForecastResponse(**item) for item in json.loads(cached_data)]
    
    params = {
        "lat": lat,
        "lon": lon,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "it"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_OPENWEATHER_URL}/forecast", params=params)
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Servizio meteo non disponibile.")
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Errore nel recupero delle previsioni meteo.")
    
    forecast = response.json()

    days = defaultdict(list)

    for item in forecast["list"]:
        date = parser.parse(item["dt_txt"]).date()
        days[date].append(item)
    
    daily_forecast = []
    for d, items in days.items():
        temps = [item["main"]["temp"] for item in items]
        icons = [item["weather"][0]["icon"] for item in items]

        min_temperature = round(min(temps))
        max_temperature = round(max(temps))

        icon = max(set(icons), key=icons.count)

        daily_forecast.append({
            "date": d.strftime("%d %b"),
            "min_temperature": min_temperature,
            "max_temperature": max_temperature,
            "icon": icon
        })

    if redis:
        await redis.set(cache_key, json.dumps(daily_forecast), ex=CACHE_TTL_FORECAST)
    
    return daily_forecast