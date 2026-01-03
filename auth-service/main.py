import jwt
import os

from fastapi import FastAPI, HTTPException, status, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import OAuth2PasswordBearer

from passlib.context import CryptContext

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from datetime import datetime, timedelta

from schemas import UserRegister, UserLogin, UserOutput, UserAdditionalFields, UserPasswordUpdate
from models import User
from database import engine, Base, get_db

PRIVATE_KEY = os.getenv("JWT_PRIVATE_KEY", "PRIVATE_KEY")
PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
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
-----END RSA PRIVATE KEY-----"""

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
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def check_existing_user(db: AsyncSession, email: str):
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalars().first()
    return user is not None

async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalars().first()

def create_access_token(data: dict, expires_delta: timedelta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)):
    to_encode = data.copy()
    expire = datetime.now() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, PRIVATE_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(jwt_token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(jwt_token, PUBLIC_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token di accesso scaduto.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token di accesso non valido.")

async def get_current_user(db: AsyncSession, jwt_token: str):
    payload = decode_access_token(jwt_token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utente mancante nel token.")
    
    result = await db.execute(select(User).filter(User.id == user_id))
    db_user = result.scalars().first()
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utente non trovato.")
    
    return db_user


app = FastAPI(title="Auth Service")

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

@app.post("/login")
async def login(user: UserLogin, db : AsyncSession = Depends(get_db)):
    db_user = await get_user_by_email(db, user.email)
    if not db_user or not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Credenziali non valide.")

    access_token = create_access_token(data={"sub": db_user.id})

    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register")
async def register(user: UserRegister, db : AsyncSession = Depends(get_db)):
    if await check_existing_user(db, user.email):
        raise HTTPException(status_code=400, detail="Indirizzo email già in uso.")
    
    hashed_password = pwd_context.hash(user.password)
    new_user = User(
        name=user.name,
        email=user.email,
        hashed_password=hashed_password
    )

    db.add(new_user)
    try:
        await db.commit()
        await db.refresh(new_user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Errore durante la registrazione dell'utente.")
    
    return {"message": "Utente registrato con successo."}

@app.get("/users/me", response_model=UserOutput)
async def get_user(token: str = Depends(oauth2_scheme), db : AsyncSession = Depends(get_db)):
    db_user = await get_current_user(db, token)
    return db_user

@app.put("/users/me", response_model=UserOutput)
async def update_user(updated_data: UserAdditionalFields, token: str = Depends(oauth2_scheme),db : AsyncSession = Depends(get_db)):
    db_user = await get_current_user(db, token)

    if updated_data.phone is not None: db_user.phone = updated_data.phone
    if updated_data.bio is not None: db_user.bio = updated_data.bio
    if updated_data.location is not None: db_user.location = updated_data.location
    if updated_data.birthdate is not None: db_user.birthdate = updated_data.birthdate

    try:
        await db.commit()
        await db.refresh(db_user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Errore durante l'aggiornamento dell'utente.")

    return db_user

@app.put("/users/me/password")
async def change_password(password_data: UserPasswordUpdate, token: str = Depends(oauth2_scheme), db : AsyncSession = Depends(get_db)):
    db_user = await get_current_user(db, token)

    if not pwd_context.verify(password_data.current_password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="La password attuale non è corretta.")

    new_hashed_password = pwd_context.hash(password_data.password)
    db_user.hashed_password = new_hashed_password

    try:
        await db.commit()
        await db.refresh(db_user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Errore durante l'aggiornamento della password.")

    return {"message": "Password aggiornata con successo."}