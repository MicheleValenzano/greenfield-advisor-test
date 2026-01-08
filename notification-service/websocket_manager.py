from fastapi import WebSocket
from typing import Dict, Set
import asyncio
import json

class WebSocketManager:
    """
    Gestore per le connessioni WebSocket attive e dell'invio di notifiche.
    Le connessioni sono organizzate per "field" per consentire l'invio mirato delle notifiche.
    """
    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}
        self.lock = asyncio.Lock() # Lock per gestire l'accesso concorrente alle connessioni
    
    async def connect(self, websocket: WebSocket, field: str):
        """
        Aggiunge una nuova connessione WebSocket per un campo specifico.
        Args:
            websocket (WebSocket): La connessione WebSocket da aggiungere.
            field (str): Il campo associato alla connessione.
        """
        async with self.lock:
            if field not in self.connections:
                self.connections[field] = set()
            self.connections[field].add(websocket)
    
    async def disconnect(self, websocket: WebSocket, field: str):
        """
        Rimuove una connessione WebSocket per un campo specifico.
        Args:
            websocket (WebSocket): La connessione WebSocket da rimuovere.
            field (str): Il campo associato alla connessione.
        """
        async with self.lock:
            if field in self.connections:
                self.connections[field].discard(websocket)
                if not self.connections[field]:
                    del self.connections[field]
    
    async def send_notification(self, field: str, message: dict):
        """
        Invia una notifica a tutte le connessioni WebSocket associate a un campo specifico.
        Gestisce le connessioni ancora presenti ma non valide rimuovendole.
        Args:
            field (str): Il campo a cui inviare la notifica.
            message (dict): Il messaggio di notifica da inviare.
        """
        async with self.lock:
            websockets = self.connections.get(field, set()).copy()

        if not websockets:
            return

        dead_websockets = []
        message = json.dumps(message)

        for websocket in websockets:
            try:
                await websocket.send_text(message)
            except Exception:
                dead_websockets.append(websocket)
        
        if dead_websockets:
            async with self.lock:
                if field in self.connections:
                    for websocket in dead_websockets:
                        self.connections[field].discard(websocket)
                        if not self.connections[field]:
                            del self.connections[field]