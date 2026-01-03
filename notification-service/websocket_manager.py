from fastapi import WebSocket
from typing import Dict, Set
import asyncio
import json

class WebSocketManager:
    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}
        self.lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, field: str):
        await websocket.accept()
        async with self.lock:
            if field not in self.connections:
                self.connections[field] = set()
            self.connections[field].add(websocket)
    
    async def disconnect(self, websocket: WebSocket, field: str):
        async with self.lock:
            if field in self.connections:
                self.connections[field].discard(websocket)
                if not self.connections[field]:
                    del self.connections[field]
    
    async def send_notification(self, field: str, message: dict):

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