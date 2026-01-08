from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from base import BaseContext

# Contesto per la rule analysis
@dataclass
class RuleAnalysisContext(BaseContext):
    """
    Contesto per l'analisi delle regole.
    Contiene la sessione del database asincrona e la connessione Redis.
    """
    db: AsyncSession
    redis: aioredis.Redis

# Contesto per il modello di ML
@dataclass
class MLAnalysisContext(BaseContext):
    """
    Contesto per l'analisi del modello di machine learning.
    Contiene il payload con i dati necessari per l'analisi.
    """
    pass