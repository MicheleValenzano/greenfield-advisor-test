from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from dataclasses import dataclass

@dataclass
class BaseContext:
    payload: dict

T = TypeVar('T', bound=BaseContext)

class AnalysisStrategy(ABC, Generic[T]):

    @abstractmethod
    async def analyze(self, context: T) -> Any:
        """Restituisce il risultato dell'analisi."""
        pass