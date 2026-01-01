from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from base import BaseContext

# Contesto per la rule analysis
@dataclass
class RuleAnalysisContext(BaseContext):
    db: AsyncSession
    redis: aioredis.Redis

# Contesto per il modello di ML
@dataclass
class MLAnalysisContext(BaseContext):
    pass