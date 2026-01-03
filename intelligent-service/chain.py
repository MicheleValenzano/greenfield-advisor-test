from dataclasses import dataclass
from typing import Any, Dict, Optional, List
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
from analyzer import IntelligentAnalyzer
from contexts import MLAnalysisContext
from field_service_client import FieldServiceClient
from httpx import HTTPStatusError

# Contesto la chain di analisi
@dataclass
class MLAnalysisChainContext:
    # payload che contiene gli identificatori necessari (field, sensor_types, window_size)
    payload: dict[str, Any]

    # token jwt per l'autenticazione con field-service
    token: Optional[str] = None

    # campi popolati durante la chain dagli handler
    raw_readings: Optional[Dict[str, List[float]]] = None # Lista di letture per ogni tipo di sensore
    statistics: Optional[List[float]] = None
    features: Optional[np.array] = None
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
    def __init__(self, field_service: FieldServiceClient, max_items: int = 50):
        super().__init__()
        self.field_service = field_service
        self.max_items = max_items
    
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        field = context.payload.get("field")
        sensor_types = context.payload.get("sensor_types", [])
        window_size = context.payload.get("window_size", self.max_items)
        token = context.token

        if context.raw_readings:
            return await self.call_next(context)
        
        if not field or not sensor_types:
            raise ValueError("Field e sensor_types sono obbligatori nel payload.")
        
        if not token:
            context.prediction = "Token di autorizzazione mancante."
            context.stop = True
            return context
        
        try:
            readings = await self.field_service.get_latest_readings(field, sensor_types, window_size, token)

            if not readings:
                context.raw_readings = {}
                context.prediction = "Rilevazioni dei sensori non disponibili."
                context.stop = True
                return context
            
            normalized_readings = {}
            for sensor_type, db_readings in readings.items():
                if isinstance(db_readings, list):
                    normalized_readings[sensor_type] = [reading['value'] for reading in db_readings if isinstance(reading, dict) and "value" in reading]
                else:
                    normalized_readings[sensor_type] = []
            
            context.raw_readings = normalized_readings
        
        except HTTPStatusError as http_err:
            context.raw_readings = {}
            error_detail = http_err.response.json().get("detail", "Errore sconosciuto.")
            context.prediction = f"Errore durante il recupero delle letture: {error_detail}"
            context.stop = True
            return context
        
        except Exception as e:
            print(f"Errore durante il recupero delle letture dei sensori: {e}")
            context.raw_readings = {}
            context.prediction = "Errore nel recupero delle letture dei sensori."
            context.stop = True
            return context
        
        return await self.call_next(context)

class FeatureExtractionHandler(ChainHandler):
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        raw_readings = context.raw_readings
        sensor_types = context.payload.get("sensor_types", [])

        if not raw_readings:
            context.prediction = "Nessuna lettura disponibile per l'estrazione delle feature."
            context.stop = True
            return context
        
        statistics = []
        missing_sensors = []
        for sensor_type in sensor_types:
            readings = raw_readings.get(sensor_type, [])
            if readings and len(readings) > 0:
                statistics.append(sum(readings) / len(readings))
            else:
                missing_sensors.append(sensor_type)
                statistics.append(0.0)
        
        if missing_sensors:
            context.prediction = f"Letture mancanti per i seguenti tipi di sensori: {', '.join(missing_sensors)}"
            context.stop = True
            return context

        context.statistics = statistics

        return await self.call_next(context)

class InputConstructionHandler(ChainHandler):
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        statistics = context.statistics
        if not statistics or len(statistics) == 0:
            context.prediction = "Statistiche non disponibili per la costruzione delle feature."
            context.stop = True
            return context

        try:
            features = statistics
            context.features = np.array(features).reshape(1, -1)
        except Exception as e:
            context.prediction = "Errore durante la costruzione delle feature."
            context.stop = True
            return context

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
            print("Prediction result:", prediction)
            print("Prediction type:", type(prediction))
            context.prediction = prediction.get("label", "N/A")
            context.confidence_score = prediction.get("confidence", 0.0)
        except Exception as e:
            print(f"Errore durante l'inferenza del modello: {e}")
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
            "Ottimale": "Le condizioni sono ideali. Mantieni il monitoraggio regolare senza interventi.",
            "Pericolo: Stress Idrico Severo": "URGENTE: Irrigare immediatamente. La pianta è in grave sofferenza. Considera di ombreggiare temporaneamente se il sole è diretto.",
            "Attenzione: Carenza Acqua": "Il terreno si sta asciugando troppo. Pianifica un ciclo di irrigazione nelle prossime ore, preferibilmente al tramonto o all'alba.",
            "Rischio: Malattie Fungine": "Umidità e calore eccessivi. Sospendi l'irrigazione fogliare, migliora la ventilazione e considera un trattamento preventivo antifungino.",
            "Attenzione: Rischio Gelata": "Temperature critiche. Proteggi le piante con tessuto non tessuto (TNT) o pacciamatura e sospendi le irrigazioni serali.",
            "Attenzione: Ristagno Idrico": "Troppa acqua nel terreno! Interrompi immediatamente l'irrigazione. Verifica il drenaggio per evitare marciumi radicali."
        }
        context.advice = advice_map.get(prediction, "Nessun consiglio disponibile per questa previsione.")

        return await self.call_next(context)

# Builder della chain
def build_ml_chain(analyzer: IntelligentAnalyzer, field_service: FieldServiceClient) -> ChainHandler:
    data_fetch_handler = DataFetchHandler(field_service=field_service)
    feature_extraction_handler = FeatureExtractionHandler()
    input_construction_handler = InputConstructionHandler()
    ml_inference_handler = MLInferenceHandler(analyzer=analyzer)
    advice_generation_handler = AdviceGenerationHandler()

    data_fetch_handler.set_next(feature_extraction_handler).set_next(input_construction_handler).set_next(ml_inference_handler).set_next(advice_generation_handler)
    return data_fetch_handler