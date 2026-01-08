from pydantic import BaseModel, Field, field_validator, EmailStr
import re
from datetime import date, datetime
from typing import Optional

# Espressioni regolari per la validazione di email, password e numero di telefono
EMAIL_PATTERN = r"^[\w\.-]+@[\w\.-]+\.\w+$" # Semplice pattern per email
PASSWORD_PATTERN = r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[!@#$%^&*?])[A-Za-z\d!@#?$%^&*]{8,}$" # Minimo 8 caratteri, almeno una lettera, un numero e un carattere speciale
PHONE_PATTERN = r"^\d{10}$" # Numero di telefono di 10 cifre senza prefisso

class UserBase(BaseModel):
    """
    Schema base per l'utente contenente email e password.
    """
    email: EmailStr = Field(..., example="mario.rossi@example.com")
    password: str = Field(..., example="SecretPassword123?")

    @field_validator("email")
    def validate_email(cls, value):
        if not re.fullmatch(EMAIL_PATTERN, value):
            raise ValueError("Indirizzo email non valido.")
        return value

    @field_validator("password")
    def validate_password(cls, value):
        if len(value) < 8:
            raise ValueError("La password deve essere lunga almeno 8 caratteri.")
        if not re.fullmatch(PASSWORD_PATTERN, value):
            raise ValueError("La password deve contenere almeno una lettera, un numero e un carattere speciale.")
        return value

class UserAdditionalFields(BaseModel):
    """
    Schema per i campi aggiuntivi (opzionali) dell'utente come telefono, biografia, posizione e data di nascita.
    """
    phone: Optional[str] = Field(None, example="1234567890")
    bio: Optional[str] = Field(None, example="Sono un agricoltore semplice.")
    location: Optional[str] = Field(None, example="Via Mola, Rutigliano, Italia")
    birthdate: Optional[date] = Field(None, example="2002-02-05")

    @field_validator("phone")
    def validate_phone_number(cls, value):
        if value and not re.fullmatch(PHONE_PATTERN, value):
            raise ValueError("Il numero di telefono deve essere lungo 10 caratteri e senza prefisso.")
        return value
    
    @field_validator("birthdate")
    def validate_birthdate(cls, value):
        if value and value > datetime.now().date():
            raise ValueError("La data di nascita non può essere nel futuro.")
        return value

class UserRegister(UserBase):
    """
    Schema per la registrazione dell'utente: include il nome, oltre a email e password.
    """
    name: str = Field(..., example="Mario Rossi")

    @field_validator("name")
    def validate_name(cls, value):
        if len(value) < 3:
            raise ValueError("Il nome deve essere lungo almeno 3 caratteri.")
        pattern = r"^[\wÀ-ÖØ-öø-ÿ'’ -]+$"
        if not re.fullmatch(pattern, value, re.UNICODE):
            raise ValueError("Il nome contiene caratteri non validi.")
        return value

class UserLogin(UserBase):
    """
    Schema per il login dell'utente, include email e password.
    """
    pass

class UserOutput(BaseModel):
    """
    Schema per l'output delle informazioni dell'utente.
    """
    id: int
    name: str
    email: str
    phone: Optional[str]
    bio: Optional[str]
    location: Optional[str]
    birthdate: Optional[date]

    class Config:
        orm_mode = True

class UserPasswordUpdate(BaseModel):
    """
    Schema per l'aggiornamento della password dell'utente.
    """
    current_password: str = Field(..., example="CurrentPassword123?")
    new_password: str = Field(..., example="NewSecretPassword123?")

    @field_validator("new_password")
    def validate_new_password(cls, value):
        if len(value) < 8:
            raise ValueError("La nuova password deve essere lunga almeno 8 caratteri.")
        if not re.fullmatch(PASSWORD_PATTERN, value):
            raise ValueError("La nuova password deve contenere almeno una lettera, un numero e un carattere speciale.")
        return value