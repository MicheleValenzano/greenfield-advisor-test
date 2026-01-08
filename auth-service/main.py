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

PRIVATE_KEY = os.getenv("JWT_PRIVATE_KEY", "PRIVATE_KEY").replace("\\n", "\n")

PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "PUBLIC_KEY").replace("\\n", "\n")

ALGORITHM = "RS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 # Solo per DEV, poi metto 60

# OAuth2 scheme per l'estrazione del token dagli header delle richieste
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Oggetto per la gestione della crittografia delle password
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def check_existing_user(db: AsyncSession, email: str):
    """
    Verifica se un utente con l'email specificata esiste già nel database.
    Args:
        db (AsyncSession): Sessione asincrona del database.
        email (str): Indirizzo email di cui verificare l'eventuale esistenza.
    Returns:
        bool: True se l'utente esiste, False altrimenti.
    """
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalars().first()
    return user is not None

async def get_user_by_email(db: AsyncSession, email: str):
    """
    Recupera un utente dal database in base all'email.
    Args:
        db (AsyncSession): Sessione asincrona del database.
        email (str): Indirizzo email dell'utente da recuperare.
    Returns:
        User | None: L'istanza dell'utente se trovato, None altrimenti
    """
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalars().first()

def create_access_token(data: dict, expires_delta: timedelta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)):
    """
    Crea un token di accesso JWT.
    Args:
        data (dict): Dati da includere nel payload del token.
        expires_delta (timedelta): Durata di validità del token.
    Returns:
        str: Token JWT codificato.
    """
    to_encode = data.copy()
    expire = datetime.now() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, PRIVATE_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(jwt_token: str = Depends(oauth2_scheme)):
    """
    Decodifica e verifica un token di accesso JWT.
    Args:
        jwt_token (str): Token JWT da decodificare.
    Returns:
        dict: Payload decodificato del token.
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

async def get_current_user(db: AsyncSession, jwt_token: str):
    """
    Recupera l'utente corrente sulla base sul token JWT fornito.
    Args:
        db (AsyncSession): Sessione asincrona del database.
        jwt_token (str): Token JWT dell'utente.
    Returns:
        User: Istanza dell'utente corrente.
    Raises:
        HTTPException: Se l'utente non è trovato o il token è invalido.
    """
    payload = decode_access_token(jwt_token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utente mancante nel token.")
    
    result = await db.execute(select(User).filter(User.id == user_id))
    db_user = result.scalars().first()
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utente non trovato.")
    
    return db_user

# Creazione dell'app FastAPI
app = FastAPI(title="Auth Service")

@app.on_event("startup")
async def on_startup():
    """
    Evento di startup per creare le tabelle del database se non esistono già.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Gestione delle eccezioni di validazione delle richieste (errori di validazione con codice 422).
    Args:
        request (Request): La richiesta che ha causato l'errore.
        exc (RequestValidationError): L'eccezione di validazione.
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
    Gestisce le eccezioni generali non catturate.
    Args:
        request (Request): La richiesta che ha causato l'errore.
        exc (Exception): L'eccezione generica.
    Returns:
        JSONResponse: Risposta JSON con un messaggio di errore generico.
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "Errore interno del server."},
    )

@app.post("/login")
async def login(user: UserLogin, db : AsyncSession = Depends(get_db)):
    """
    Endpoint per il login dell'utente.
    Args:
        user (UserLogin): Dati di login dell'utente.
        db (AsyncSession): Sessione asincrona del database.
    Returns:
        dict: Token di accesso JWT e tipo di token (bearer).
    Raises:
        HTTPException: Se le credenziali non sono valide.
    """
    db_user = await get_user_by_email(db, user.email)
    if not db_user or not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Credenziali non valide.")

    access_token = create_access_token(data={"sub": db_user.id})

    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register")
async def register(user: UserRegister, db : AsyncSession = Depends(get_db)):
    """
    Endpoint per la registrazione di un nuovo utente.
    Args:
        user (UserRegister): Dati di registrazione dell'utente.
        db (AsyncSession): Sessione asincrona del database.
    Returns:
        dict: Messaggio di successo della registrazione.
    Raises:
        HTTPException: Se l'email è già in uso o si verifica un errore durante la registrazione.
    """
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
    """
    Endpoint per recuperare i dettagli dell'utente corrente.
    Args:
        token (str): Token di accesso JWT dell'utente.
        db (AsyncSession): Sessione asincrona del database.
    Returns:
        UserOutput: Dati dell'utente corrente.
    Raises:
        HTTPException: Se il token è invalido o l'utente non è trovato."""
    db_user = await get_current_user(db, token)
    return db_user

@app.put("/users/me", response_model=UserOutput)
async def update_user(updated_data: UserAdditionalFields, token: str = Depends(oauth2_scheme),db : AsyncSession = Depends(get_db)):
    """
    Endpoint per aggiornare i campi aggiuntivi dell'utente corrente.
    Args:
        updated_data (UserAdditionalFields): Dati aggiornati dell'utente.
        token (str): Token di accesso JWT dell'utente.
        db (AsyncSession): Sessione asincrona del database.
    Returns:
        UserOutput: Dati aggiornati dell'utente.
    Raises:
        HTTPException: Se si verifica un errore durante l'aggiornamento dell'utente
    """
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
    """
    Endpoint per aggiornare la password dell'utente corrente.
    Args:
        password_data (UserPasswordUpdate): password attuale e nuova password.
        token (str): Token di accesso JWT dell'utente.
        db (AsyncSession): Sessione asincrona del database.
    Returns:
        dict: Messaggio di successo dell'aggiornamento della password.
    Raises:
        HTTPException: Se la password attuale non è corretta o si verifica un errore durante l'aggiornamento della password.
    """
    db_user = await get_current_user(db, token)

    if not pwd_context.verify(password_data.current_password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="La password attuale non è corretta.")

    new_hashed_password = pwd_context.hash(password_data.new_password)
    db_user.hashed_password = new_hashed_password

    try:
        await db.commit()
        await db.refresh(db_user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Errore durante l'aggiornamento della password.")

    return {"message": "Password aggiornata con successo."}