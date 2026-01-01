from base import AnalysisStrategy, BaseContext
from typing import Generic, TypeVar

T = TypeVar('T', bound=BaseContext)

class IntelligentAnalyzer(Generic[T]):
    def __init__(self, strategy: AnalysisStrategy[T]):
        self.strategy = strategy

    async def execute(self, context: T):
        return await self.strategy.analyze(context)