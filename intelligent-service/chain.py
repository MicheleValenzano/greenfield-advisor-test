from dataclasses import dataclass
from typing import Any, Dict, Optional, List
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
from analyzer import IntelligentAnalyzer
from contexts import MLAnalysisContext

# Contesto la chain di analisi
@dataclass
class MLAnalysisChainContext:
    # payload che contiene gli identificatori necessari (field, sensor_types, window_size)
    payload: dict[str, Any]

    # campi popolati durante la chain dagli handler
    raw_readings: Optional[List[Dict[str, Any]]] = None # Lista di letture per ogni tipo di sensore
    statistics: Optional[List[float]] = None
    features: Optional[List[float]] = None
    prediction: Optional[str] = None
    confidence_score: Optional[float] = None
    advice: Optional[str] = None

    # flag che permette di interrompere la catena se necessario
    stop: bool = False

# Interfaccia per gli handler della chain
class ChainHandler(ABC):
    def __init__(self):
        self.next_handler: Optional['ChainHandler'] = None
    
    def set_next(self, handler: 'ChainHandler') -> 'ChainHandler':
        self.next_handler = handler
        return handler
    
    async def call_next(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        if self.next_handler and not context.stop:
            return await self.next_handler.handle(context)
        return context
    
    @abstractmethod
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        pass

# Handler concreti della chain
class DataFetchHandler(ChainHandler):
    def __init__(self, db: AsyncSession, max_items: int = 50):
        super().__init__()
        self.db = db
        self.max_items = max_items
    
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        field = context.payload.get("field")
        sensor_types = context.payload.get("sensor_types", [])
        window_size = context.payload.get("window_size", self.max_items)

        if context.raw_readings:
            return await self.call_next(context)
        
        if not field or not sensor_types:
            raise ValueError("Field e sensor_types sono obbligatori nel payload.")
        
        try:
            # chiedi a field-service le letture di ogni sensor_type TODO
            readings = []

            if not readings: # cambiare con la risposta del servizio
                context.raw_readings = []
                context.prediction = "Rilevazioni dei sensori non disponibili."
                context.stop = True
                return context
            
        except Exception as e:
            context.raw_readings = []
            context.prediction = "Errore nel recupero delle letture dei sensori."
            context.stop = True
            return context
        
        return await self.call_next(context)

class FeatureExtractionHandler(ChainHandler):
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        raw_readings = context.raw_readings or context.payload.get("raw_readings", [])
        if not raw_readings:
            context.prediction = "Nessuna lettura disponibile per l'estrazione delle feature."
            context.stop = True
            return context
        
        statistics = [sum(readings) / len(readings) if readings else 0.0 for readings in raw_readings]
        context.statistics = statistics

        return await self.call_next(context)

class InputConstructionHandler(ChainHandler):
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        statistics = context.statistics
        if not statistics:
            context.prediction = "Statistiche non disponibili per la costruzione delle feature."
            context.stop = True
            return context
        
        features = statistics
        context.features = np.array(features).reshape(1, -1)

        return await self.call_next(context)

class MLInferenceHandler(ChainHandler):
    def __init__(self, analyzer: IntelligentAnalyzer):
        super().__init__()
        self.analyzer = analyzer
    
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        features = context.features
        if features is None:
            context.prediction = "Feature non disponibili per l'inferenza."
            context.stop = True
            return context
        
        try:
            prediction = await self.analyzer.execute(MLAnalysisContext(payload={"features": features}))
            context.prediction = prediction.get("label", "N/A")
            context.confidence_score = prediction.get("confidence", 0.0)
        except Exception as e:
            context.prediction = "Errore durante l'inferenza del modello."
            context.confidence_score = 0.0
            context.stop = True
            return context
        
        return await self.call_next(context)

class AdviceGenerationHandler(ChainHandler):
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        prediction = context.prediction
        if not prediction:
            context.advice = "Nessuna previsione disponibile per generare consigli."
            return context
        
        advice_map = {
            "ottimale": "I parametri sono nella norma. Nessuna azione richiesta.",
            "attenzione": "Monitorare l'irrigazione nelle prossime ore.",
            "critico": "Irrigazione necessaria immediatamente!"
        }
        context.advice = advice_map.get(prediction.lower(), "Nessun consiglio disponibile per questa previsione.")

        return await self.call_next(context)

# Builder della chain
def build_ml_chain(db: AsyncSession, analyzer: IntelligentAnalyzer) -> ChainHandler:
    data_fetch_handler = DataFetchHandler(db=db)
    feature_extraction_handler = FeatureExtractionHandler()
    input_construction_handler = InputConstructionHandler()
    ml_inference_handler = MLInferenceHandler(analyzer=analyzer)
    advice_generation_handler = AdviceGenerationHandler()

    data_fetch_handler.set_next(feature_extraction_handler).set_next(input_construction_handler).set_next(ml_inference_handler).set_next(advice_generation_handler)
    return data_fetch_handler