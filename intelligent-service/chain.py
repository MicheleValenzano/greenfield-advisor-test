from dataclasses import dataclass
from typing import Any, Dict, Optional, List
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
from analyzer import IntelligentAnalyzer
from contexts import MLAnalysisContext
from field_service_client import FieldServiceClient
from httpx import HTTPStatusError

# Contesto per la chain di analisi
@dataclass
class MLAnalysisChainContext:
    """
    Contesto per la catena di analisi ML.
    Contiene i dati necessari per ogni fase della catena e i risultati intermedi.

    Attributes:
        payload (dict): Dati di input per la catena, inclusi field, sensor_types e window_size.
        token (Optional[str]): Token JWT per l'autenticazione con field-service.
        raw_readings (Optional[Dict[str, List[float]]]): Letture grezze dei sensori.
        statistics (Optional[List[float]]): Statistiche calcolate dalle letture.
        features (Optional[np.array]): Feature costruite per l'inferenza ML.
        prediction (Optional[str]): Risultato della previsione ML.
        confidence_score (Optional[float]): Punteggio di confidenza della previsione.
        advice (Optional[str]): Consigli generati in base alla previsione.
        stop (bool): Flag per interrompere la catena se necessario.
    """

    # payload che contiene gli identificatori necessari (field, sensor_types, window_size)
    payload: dict[str, Any]

    # token jwt per l'autenticazione con field-service
    token: Optional[str] = None

    # campi popolati durante la chain dagli handler
    raw_readings: Optional[Dict[str, List[float]]] = None
    statistics: Optional[List[float]] = None
    features: Optional[np.array] = None
    prediction: Optional[str] = None
    confidence_score: Optional[float] = None
    advice: Optional[str] = None

    # flag che permette di interrompere la catena se necessario
    stop: bool = False

# Interfaccia per gli handler della chain
class ChainHandler(ABC):
    """
    Interfaccia astratta per gli handler della catena.
    Ogni handler deve implementare il metodo handle per processare il contesto.
    """
    def __init__(self):
        self.next_handler: Optional['ChainHandler'] = None
    
    def set_next(self, handler: 'ChainHandler') -> 'ChainHandler':
        """
        Imposta il prossimo handler nella catena.
        Args:
            handler (ChainHandler): Il prossimo handler da eseguire.
        Returns:
            ChainHandler: Il prossimo handler.
        """
        self.next_handler = handler
        return handler
    
    async def call_next(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        """
        Chiama il prossimo handler nella catena se esiste e se il flag stop non è impostato.
        Args:
            context (MLAnalysisChainContext): Il contesto da passare al prossimo handler.
        Returns:
            MLAnalysisChainContext: Il contesto dopo l'elaborazione del prossimo handler.
        """
        if self.next_handler and not context.stop:
            return await self.next_handler.handle(context)
        return context
    
    @abstractmethod
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        """
        Metodo astratto per processare il contesto.
        Args:
            context (MLAnalysisChainContext): Il contesto da processare.
        Returns:
            MLAnalysisChainContext: Il contesto dopo l'elaborazione.
        """
        pass

# Handler concreti della chain
class DataFetchHandler(ChainHandler):
    """
    Handler per il recupero delle letture dei sensori dal field-service.
    Args:
        field_service (FieldServiceClient): Client per interagire con il field-service.
        max_items (int): Numero massimo di letture da recuperare per sensore.
    """
    def __init__(self, field_service: FieldServiceClient, max_items: int = 50):
        super().__init__()
        self.field_service = field_service
        self.max_items = max_items
    
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        """
        Recupera le letture dei sensori dal field-service e le normalizza.
        Args:
            context (MLAnalysisChainContext): Il contesto contenente i parametri per il recupero delle letture.
        Returns:
            MLAnalysisChainContext: Il contesto aggiornato con le letture dei sensori.
        """
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
    """
    Handler per l'estrazione delle feature dalle letture dei sensori.
    Calcola statistiche semplici (media) per ogni tipo di sensore.
    """
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        """
        Estrae le feature dalle letture dei sensori calcolando la media per ogni tipo di sensore.
        Args:
            context (MLAnalysisChainContext): Il contesto contenente le letture dei sensori.
        Returns:
            MLAnalysisChainContext: Il contesto aggiornato con le statistiche calcolate.
        """
        try:
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
        except Exception as e:
            context.prediction = "Errore durante l'estrazione delle feature."
            context.stop = True
            return context

        return await self.call_next(context)

class InputConstructionHandler(ChainHandler):
    """
    Handler per la costruzione dell'input per l'inferenza ML.
    Trasforma le statistiche in un array numpy adatto per il modello ML.
    """
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        """
        Costruisce l'input per l'inferenza ML trasformando le statistiche in un array numpy.
        Args:
            context (MLAnalysisChainContext): Il contesto contenente le statistiche calcolate.
        Returns:
            MLAnalysisChainContext: Il contesto aggiornato con le feature costruite."""
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
    """
    Handler per l'inferenza del modello ML.
    Utilizza l'IntelligentAnalyzer per ottenere la previsione basata sulle feature.
    Args:
        analyzer (IntelligentAnalyzer): Analizzatore intelligente per l'inferenza ML.
    """
    def __init__(self, analyzer: IntelligentAnalyzer):
        super().__init__()
        self.analyzer = analyzer
    
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        """
        Esegue l'inferenza del modello ML utilizzando l'IntelligentAnalyzer.
        Args:
            context (MLAnalysisChainContext): Il contesto contenente le feature per l'inferenza.
        Returns:
            MLAnalysisChainContext: Il contesto aggiornato con la previsione e il punteggio di confidenza.
        """
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
    """
    Handler per la generazione dei consigli basati sulla previsione ML.
    Mappa le etichette di previsione a consigli specifici per l'utente.
    """
    async def handle(self, context: MLAnalysisChainContext) -> MLAnalysisChainContext:
        """
        Genera consigli basati sulla previsione ML.
        Args:
            context (MLAnalysisChainContext): Il contesto contenente la previsione ML.
        Returns:
            MLAnalysisChainContext: Il contesto aggiornato con i consigli generati.
        """
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
    """
    Costruisce la catena di handler per l'analisi ML.
    Args:
        analyzer (IntelligentAnalyzer): Analizzatore intelligente per l'inferenza ML.
        field_service (FieldServiceClient): Client per interagire con il field-service.
    Returns:
        ChainHandler: Il primo handler della catena.
    """
    data_fetch_handler = DataFetchHandler(field_service=field_service)
    feature_extraction_handler = FeatureExtractionHandler()
    input_construction_handler = InputConstructionHandler()
    ml_inference_handler = MLInferenceHandler(analyzer=analyzer)
    advice_generation_handler = AdviceGenerationHandler()

    data_fetch_handler.set_next(feature_extraction_handler).set_next(input_construction_handler).set_next(ml_inference_handler).set_next(advice_generation_handler)
    return data_fetch_handler