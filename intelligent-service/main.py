from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from fastapi.exceptions import RequestValidationError
from schemas import RuleCreation, RuleOutput
from models import Rule, Alert
from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from database import engine, Base, get_db
import jwt
import os
import httpx
from contextlib import asynccontextmanager
import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool
from consumer import RabbitMQIntelligentConsumer
from contexts import MLAnalysisContext, RuleAnalysisContext
from ml_strategy import MLStrategy
from rule_strategy import RuleBasedStrategy
from analyzer import IntelligentAnalyzer
from datetime import datetime, timezone
import joblib
from chain import MLAnalysisChainContext, build_ml_chain, ChainHandler
from field_service_client import FieldServiceClient
from functools import lru_cache

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbit-mq/")
RABBITMQ_INTELLIGENT_QUEUE = os.getenv("RABBITMQ_INTELLIGENT_QUEUE", "sensor-readings-queue")
RABBITMQ_ALERTS_EXCHANGE = os.getenv("RABBITMQ_ALERTS_EXCHANGE", "alerts.topic")

FIELD_SERVICE_URL = os.getenv("FIELD_SERVICE_URL", "http://field-service:8004")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis-intelligent:6379")
REDIS_MAX_CONNECTIONS = 20

CACHE_TTL_RULES = 5 * 60

consumer: RabbitMQIntelligentConsumer = None

PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "PUBLIC_KEY")
PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEApXtfAxVV015pQOx026do
IkRAVcRW9VieD0DSvP4PxQl055CBnJh42DrdshKWNvfSJ98OxH5Hz9WGMQHit1hQ
HJwAC0/bue2sa5HoaH/0o7eyFVYnui+3YrYOYO/a2zG4qiSmkVwvOy/L+uymaAjl
Y4fGzcf8TRMWEUZ7A4pIhvTuSMgRDyobVVmoBiKzvbAPqs3ggP8Vmd//hXovaSww
JugwkvSVQvDaeRjKk2ENbwrA85BxtblE/sA1OKN0RQo1jkOECKuhi9nPhrRrtMs8
MChlLW9GrBagFZVFA9LCTCSAXIWlzQIWNhUlh96/ih12KG3ynuXxxuggF9GeWLUl
jtTXJSY6LyHmsRUsgC17S7sTyIYXmW4gJj4qXWGeVqRwsPj+aWQBYyi5IyBXH7gV
iqJT39xgWLl81dYpO7B0Jx4zIc9MfYltsXXUxFDRuOftDQKKJ4bKDIdbjko3giUC
A2LY9dJjJXB4j5wovqVJnDU4vrdgGmxZklRoaQq0dkWlhGAH982cQ1A6mfEOsDgc
yO5xVZNmlQ7cVuNjyZ1Wr1Hcc4UYNSibzx6Y+8C4/x6jBodBxHofAPYR/jrFoLAu
ACgboGEVD48oNVAd7XRnjXcOvu+kvRhLjwO6VoOJeRfArPAkXmL7pelkqY5RFcvg
h8XIDNY39jp5TDH4Pa8/Q8MCAwEAAQ==
-----END PUBLIC KEY-----"""

ALGORITHM = "RS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

MODEL_PATH = "greenfield_model.pkl"
model = None
ml_strategy_instance = None

rule_strategy_instance = RuleBasedStrategy()

def get_rule_analyzer() -> IntelligentAnalyzer[RuleAnalysisContext]:
    return IntelligentAnalyzer(strategy=rule_strategy_instance)

def get_ml_analyzer() -> IntelligentAnalyzer[MLAnalysisContext]:
    return IntelligentAnalyzer(strategy=ml_strategy_instance)

@lru_cache()
def get_field_service_client(request: Request) -> FieldServiceClient:
    return FieldServiceClient(client=request.app.state.field_service_client)

def get_ml_chain_real(analyzer: IntelligentAnalyzer[MLAnalysisContext] = Depends(get_ml_analyzer), field_service: FieldServiceClient = Depends(get_field_service_client)) -> ChainHandler:
    return build_ml_chain(analyzer=analyzer, field_service=field_service)

def decode_access_token(jwt_token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(jwt_token, PUBLIC_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token di accesso scaduto.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token di accesso non valido.")

@asynccontextmanager
async def lifespan(app: FastAPI):

    try:
        global model
        model = joblib.load(MODEL_PATH)
        global ml_strategy_instance
        ml_strategy_instance = MLStrategy(model=model)
    except Exception as e:
        print("Errore nel caricamento del modello ML:", e)
        ml_strategy_instance = None

    rule_analyzer = get_rule_analyzer()

    app.state.field_service_client = httpx.AsyncClient(base_url=FIELD_SERVICE_URL, timeout=httpx.Timeout(5.0))
    app.state.fields_client = httpx.AsyncClient(base_url=FIELD_SERVICE_URL, timeout=httpx.Timeout(5.0))

    global consumer
    consumer = RabbitMQIntelligentConsumer(RABBITMQ_URL, RABBITMQ_INTELLIGENT_QUEUE, RABBITMQ_ALERTS_EXCHANGE, rule_analyzer, REDIS_URL, REDIS_MAX_CONNECTIONS)
    await consumer.connect()

    try:
        pool = ConnectionPool.from_url(REDIS_URL, max_connections=REDIS_MAX_CONNECTIONS)
        app.state.redis = aioredis.Redis(decode_responses=True, connection_pool=pool)
    except Exception:
        app.state.redis = None

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    if consumer:
        await consumer.close()
    await app.state.fields_client.aclose()
    await app.state.field_service_client.aclose()
    if app.state.redis:
        await app.state.redis.close()

def get_redis(request: Request):
    return getattr(request.app.state, "redis", None)

app = FastAPI(title="Intelligent Service", lifespan=lifespan)

def get_fields_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.fields_client

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
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
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "Errore interno del server."},
    )

@app.post("/rules", status_code=201, response_model=RuleOutput)
async def create_rule(rule: RuleCreation, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token), fields_client: httpx.AsyncClient = Depends(get_fields_client), redis: aioredis.Redis = Depends(get_redis)):
    
    cache_key = f"rule_validation:{token['sub']}:{rule.field}:{rule.sensor_type}"

    if redis:
        try:
            cached_data = await redis.get(cache_key)
            print("Cached data:", cached_data)
        except Exception:
            cached_data = None
    
    if cached_data == "1":
        pass # Autorizzazione già validata in cache
    elif cached_data == "0":
        raise HTTPException(status_code=403, detail="Non hai i permessi per creare regole su questo campo.")
    else:
        try:
            resp = await fields_client.get(f"/internal/validate-rule", params={"field": rule.field, "sensor_type": rule.sensor_type, "user_id": token["sub"]})
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Validazione della regola non disponibile.")
        
        if resp.status_code == 200:
            if redis:
                try:
                    await redis.set(cache_key, "1", ex=CACHE_TTL_RULES)
                except Exception:
                    pass
        elif resp.status_code == 403:
            if redis:
                try:
                    await redis.set(cache_key, "0", ex=CACHE_TTL_RULES)
                except Exception:
                    pass
            raise HTTPException(status_code=403, detail="Non hai i permessi per creare regole su questo campo.")
        else:
            raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail", resp.text))

    result = await db.execute(select(Rule).where(
        Rule.sensor_type == rule.sensor_type,
        Rule.condition == rule.condition,
        Rule.threshold == rule.threshold,
        Rule.message == rule.message,
        Rule.field == rule.field,
        Rule.owner_id == token["sub"]
    ))
    existing_rule = result.scalars().first()
    if existing_rule:
        raise HTTPException(status_code=400, detail="Esiste già una regola identica per questo utente.")

    new_rule = Rule(
        sensor_type=rule.sensor_type,
        condition=rule.condition,
        threshold=rule.threshold,
        message=rule.message,
        field=rule.field,
        owner_id=token["sub"]
    )

    db.add(new_rule)
    try:
        await db.commit()
        await db.refresh(new_rule)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Errore del database durante la creazione della regola.")
    
    if redis:
        try:
            await redis.delete(f"rules_list:{rule.field}")
        except Exception:
            print("Errore nella cancellazione della cache delle regole.")
    
    return new_rule

@app.delete("/rules/{rule_name}", status_code=200)
async def delete_rule(rule_name: str, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token), redis: aioredis.Redis = Depends(get_redis)):
    result = await db.execute(select(Rule).where(Rule.rule_name == rule_name))
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Regola non trovata.")
    
    if rule.owner_id != token["sub"]:
        raise HTTPException(status_code=403, detail="Non hai i permessi per eliminare questa regola.")
    
    field_to_invalidate = rule.field

    try:
        await db.delete(rule)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Errore del database durante l'eliminazione della regola.")
    
    if redis:
        try:
            await redis.delete(f"rules_list:{field_to_invalidate}")
        except Exception:
            print("Errore nella cancellazione della cache delle regole.")
    
    return {"message": "Regola eliminata con successo."}

@app.get("/rules", status_code=200, response_model=list[RuleOutput])
async def list_rules(field: str, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    result = await db.execute(select(Rule).where(Rule.field == field, Rule.owner_id == token["sub"]))
    rules = result.scalars().all()

    return rules

@app.post("/archive-alerts", status_code=200)
async def archive_all_alerts(db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    cutoff = datetime.now(timezone.utc)
    query = update(Alert).where(Alert.owner_id == token["sub"], Alert.active == True, Alert.timestamp <= cutoff).values(active=False)
    await db.execute(query)
    await db.commit()

    return {"message": "Tutti gli alert attivi sono stati archiviati."}

@app.get("/alerts")
async def list_alerts(limit: int, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):

    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="Il parametro 'limit' deve essere compreso tra 1 e 100.")

    result = await db.execute(select(Alert).where(Alert.owner_id == token["sub"], Alert.active == True).order_by(desc(Alert.timestamp)).limit(limit))
    alerts = result.scalars().all()

    return alerts

@app.post("/archive-alerts/{field}", status_code=200)
async def archive_field_alerts(field: str, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):
    cutoff = datetime.now(timezone.utc)
    query = update(Alert).where(Alert.owner_id == token["sub"], Alert.field == field, Alert.active == True, Alert.timestamp <= cutoff).values(active=False)
    await db.execute(query)
    await db.commit()

    return {"message": f"Tutti gli alert attivi del campo sono stati archiviati."}

# Recupero tutti gli alert della field specificata, limitati da un parametro 'limit'
@app.get("/alerts/{field}", status_code=200)
async def list_field_alerts(field: str, limit: int, db: AsyncSession = Depends(get_db), token: dict = Depends(decode_access_token)):

    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="Il parametro 'limit' deve essere compreso tra 1 e 100.")

    result = await db.execute(select(Alert).where(Alert.owner_id == token["sub"], Alert.field == field, Alert.active == True).order_by(desc(Alert.timestamp)).limit(limit))
    alerts = result.scalars().all()

    return alerts

@app.get("/ai-prediction", status_code=200)
async def ai_prediction(field: str, chain: ChainHandler = Depends(get_ml_chain_real), db: AsyncSession = Depends(get_db), token_payload: dict = Depends(decode_access_token), raw_jwt_token: str = Depends(oauth2_scheme)):

    if not model:
        raise HTTPException(503, detail="Modello di Machine Learning non disponibile.")
    
    target_sensors = ["temperature", "humidity", "soil_moisture"] # Poi metterli in uppercase magari

    context = MLAnalysisChainContext(
        payload={
            'field': field,
            'sensor_types': target_sensors,
            'window_size': 50
        },
        token=raw_jwt_token
    )

    try:
        final_context = await chain.handle(context)

        formatted_input = None
        
        if final_context.features is not None:
            values_list = final_context.features.flatten().tolist()
        
            # Dizionario con accoppiamento sensore - valore medio
            if len(values_list) == len(target_sensors):
                formatted_input = dict(zip(target_sensors, values_list))
            else:
                formatted_input = values_list

        return {
            "status": final_context.prediction,
            "advice": final_context.advice,
            "confidence": final_context.confidence_score,
            "details": {
                'input_recieved': formatted_input,
            }
        }
    except Exception as e:
        print(f"Errore durante l'analisi Machine Learning: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Errore durante l'analisi Machine Learning: {str(e)}")