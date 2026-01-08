import json
from aio_pika import connect_robust, IncomingMessage, ExchangeType
from websocket_manager import WebSocketManager

class RabbitMQNotificationConsumer:
    """
    Consuma messaggi da RabbitMQ e inoltra le notifiche ai client WebSocket.
    Ascolta due exchange: uno per le letture dei sensori e uno per gli alert.

    Attributes:
        rabbitmq_url (str): URL di connessione a RabbitMQ.
        sensors_exchange_name (str): Nome dell'exchange per le letture dei sensori.
        alerts_exchange_name (str): Nome dell'exchange per gli alert.
        field_routing_key (str): Routing key per le letture dei sensori.
        alerts_routing_key (str): Routing key per gli alert.
        websocket_manager (WebSocketManager): Gestore delle connessioni WebSocket.
    """
    def __init__(self, rabbitmq_url: str, 
                 sensors_exchange_name: str, 
                 alerts_exchange_name: str,
                 field_routing_key: str,
                 alerts_routing_key: str,
                 websocket_manager: WebSocketManager):
        self.rabbitmq_url = rabbitmq_url
        self.sensors_exchange_name = sensors_exchange_name
        self.alerts_exchange_name = alerts_exchange_name
        self.websocket_manager = websocket_manager
        self.field_routing_key = field_routing_key
        self.alerts_routing_key = alerts_routing_key
        self.connection = None
        self.channel = None
        self.sensors_exchange = None
        self.alerts_exchange = None
    
    async def connect(self):
        """
        Stabilisce la connessione a RabbitMQ e configura gli exchange e le code.
        """
        self.connection = await connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()

        await self.channel.set_qos(prefetch_count=10)

        self.sensors_exchange = await self.channel.declare_exchange(self.sensors_exchange_name, ExchangeType.TOPIC, durable=True)
        self.alerts_exchange = await self.channel.declare_exchange(self.alerts_exchange_name, ExchangeType.TOPIC, durable=True)

        readings_queue = await self.channel.declare_queue("", exclusive=True)
        await readings_queue.bind(self.sensors_exchange, routing_key=self.field_routing_key)

        alerts_queue = await self.channel.declare_queue("", exclusive=True)
        await alerts_queue.bind(self.alerts_exchange, routing_key=self.alerts_routing_key)

        await readings_queue.consume(self.handle_reading_message)
        await alerts_queue.consume(self.handle_alert_message)

    async def handle_reading_message(self, message: IncomingMessage):
        """
        Gestisce i messaggi relativi alle nuove letture dei sensori.
        Inoltra la lettura ai client WebSocket interessati.
        Args:
            message (IncomingMessage): Il messaggio ricevuto da RabbitMQ.
        """
        async with message.process():
            payload = json.loads(message.body.decode())
            field = payload["field_id"]
            print("Received reading for field:", field, "payload:", payload)
            if field:
                envelope = {
                    "type": "reading",
                    "data": payload
                }
                await self.websocket_manager.send_notification(field, message=envelope)
    
    async def handle_alert_message(self, message: IncomingMessage):
        """
        Gestisce i messaggi relativi agli alert.
        Inoltra l'alert ai client WebSocket interessati.
        Args:
            message (IncomingMessage): Il messaggio ricevuto da RabbitMQ.
        """
        async with message.process():
            payload = json.loads(message.body.decode())
            field = payload["field"]
            print("Received alert for field:", field, "payload:", payload)
            if field:
                envelope = {
                    "type": "alert",
                    "data": payload
                }
                await self.websocket_manager.send_notification(field, message=envelope)
    
    async def close(self):
        if self.connection:
            await self.connection.close()