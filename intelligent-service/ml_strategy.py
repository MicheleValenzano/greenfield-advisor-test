from base import AnalysisStrategy
from contexts import MLAnalysisContext

class MLStrategy(AnalysisStrategy):
    def __init__(self, model):
        self.model = model

    async def analyze(self, context: MLAnalysisContext):
        
        # TODO

        result = self.model.predict(context.payload["features"])
        return result