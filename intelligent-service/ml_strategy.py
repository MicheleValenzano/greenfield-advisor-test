from base import AnalysisStrategy
from contexts import MLAnalysisContext
import numpy as np

class MLStrategy(AnalysisStrategy):
    """
    Strategia di analisi basata su modelli di machine learning.
    Utilizza un modello pre-addestrato (Random Forest) per effettuare previsioni sui dati forniti.

    Attributes:
        model: Il modello di machine learning pre-addestrato utilizzato per le previsioni
    """
    def __init__(self, model):
        self.model = model

    async def analyze(self, context: MLAnalysisContext):
        """
        Esegue l'analisi utilizzando il modello di machine learning.
        Args:
            context (MLAnalysisContext): Il contesto contenente i dati per l'analisi.
        Returns:
            dict: Un dizionario contenente l'etichetta prevista e il punteggio di confidenza.
        Raises:
            ValueError: Se le feature non sono fornite o sono vuote."""
        features = context.payload["features"]

        if features is None:
            raise ValueError("Features non fornite per l'analisi ML.")
        
        if isinstance(features, np.ndarray) and features.size == 0:
            raise ValueError("Feature vuote per l'analisi ML.")

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