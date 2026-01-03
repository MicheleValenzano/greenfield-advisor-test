from base import AnalysisStrategy
from contexts import MLAnalysisContext
import numpy as np

class MLStrategy(AnalysisStrategy):
    def __init__(self, model):
        self.model = model

    async def analyze(self, context: MLAnalysisContext):

        features = context.payload["features"]

        if not features:
            raise ValueError("Features non fornite per l'analisi ML.")

        if isinstance(features, list):
            features = np.array(features).reshape(1, -1)
        elif isinstance(features, np.ndarray):
            if features.ndim == 1:
                features = features.reshape(1, -1)

        result = self.model.predict(features)[0]

        try:
            confidence_score = self.model.predict_proba(features)[0].max()
        except Exception:
            result = "Sconosciuto"
            confidence_score = 0.0
        
        return {
            "label": str(result),
            "confidence": float(confidence_score)
        }