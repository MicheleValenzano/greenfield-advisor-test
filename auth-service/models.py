from sqlalchemy import Column, Integer, String, Date
from database import Base

class User(Base):
    """
    Schema della tabella User del database per rappresentare gli utenti nel sistema di autenticazione.
    
    Attributes:
        id (int): Identificatore univoco dell'utente.
        email (str): Indirizzo email dell'utente.
        hashed_password (str): Password hashata dell'utente.
        name (str): Nome completo dell'utente.
        phone (str): Numero di telefono dell'utente.
        bio (str): Breve biografia dell'utente.
        location (str): Posizione geografica dell'utente.
        birthdate (date): Data di nascita dell'utente.
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    bio = Column(String, nullable=True)
    location = Column(String, nullable=True)
    birthdate = Column(Date, nullable=True)