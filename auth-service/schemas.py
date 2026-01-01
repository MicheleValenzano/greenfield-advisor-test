from pydantic import BaseModel, Field, field_validator, EmailStr
import re
from datetime import date, datetime
from typing import Optional

EMAIL_PATTERN = r"^[\w\.-]+@[\w\.-]+\.\w+$"
PASSWORD_PATTERN = r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[!@#$%^&*?])[A-Za-z\d!@#?$%^&*]{8,}$"
PHONE_PATTERN = r"^\d{10}$"

class UserBase(BaseModel):
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
    phone: Optional[str] = Field(None, example="1234567890")
    bio: Optional[str] = Field(None, example="Sono un agricoltore semplice.")
    location: Optional[str] = Field(None, example="Via Mola, Rutigliano, Italia")
    birthdate: Optional[date] = Field(None, example="2002-02-05")

    @field_validator("phone")
    def validate_phone_number(cls, value):
        if value and not re.fullmatch(PHONE_PATTERN, value):
            raise ValueError("Il numero di telefono deve essere lungo 10 caratteri e senza prefisso.")
    
    @field_validator("birthdate")
    def validate_birthdate(cls, value):
        if value and value > datetime.now().date():
            raise ValueError("La data di nascita non può essere nel futuro.")
        return value

class UserRegister(UserBase):
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
    pass

class UserOutput(BaseModel):
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
    current_password: str = Field(..., example="CurrentPassword123?")
    new_password: str = Field(..., example="NewSecretPassword123?")

    @field_validator("new_password")
    def validate_new_password(cls, value):
        if len(value) < 8:
            raise ValueError("La nuova password deve essere lunga almeno 8 caratteri.")
        if not re.fullmatch(PASSWORD_PATTERN, value):
            raise ValueError("La nuova password deve contenere almeno una lettera, un numero e un carattere speciale.")
        return value