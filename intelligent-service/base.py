from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from dataclasses import dataclass

@dataclass
class BaseContext:
    """
    Contesto di base per l'analisi intelligente.
    Attributes:
        payload (dict): I dati da analizzare.
    """
    payload: dict

# Definizione del tipo generico per il contesto di analisi.
T = TypeVar('T', bound=BaseContext)

class AnalysisStrategy(ABC, Generic[T]):
    """
    Strategia di analisi astratta.
    Definisce il metodo di analisi che deve essere implementato dalle strategie concrete.
    """
    @abstractmethod
    async def analyze(self, context: T) -> Any:
        """
        Restituisce il risultato dell'analisi.
        Args:
            context (T): Il contesto di analisi.
        Returns:
            Any: Il risultato dell'analisi.
        """
        pass