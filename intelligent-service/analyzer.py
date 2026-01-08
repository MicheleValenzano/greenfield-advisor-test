from base import AnalysisStrategy, BaseContext
from typing import Generic, TypeVar

# Definizione del tipo generico per il contesto di analisi.
T = TypeVar('T', bound=BaseContext)

class IntelligentAnalyzer(Generic[T]):
    """
    Analizzatore intelligente che utilizza una strategia di analisi specifica.
    Attributes:
        strategy (AnalysisStrategy[T]): La strategia di analisi da utilizzare.
    """
    def __init__(self, strategy: AnalysisStrategy[T]):
        self.strategy = strategy

    async def execute(self, context: T):
        """
        Esegue l'analisi utilizzando la strategia specificata.
        Args:
            context (T): Il contesto di analisi.
        Returns:
            Il risultato dell'analisi.
        """
        return await self.strategy.analyze(context)