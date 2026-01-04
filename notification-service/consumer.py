import json
from aio_pika import connect_robust, IncomingMessage, ExchangeType
from websocket_manager import WebSocketManager

class RabbitMQNotificationConsumer:
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
        async with message.process():
            # qui puoi personalizzare il formato del messaggio se necessario
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
        async with message.process():
            # qui puoi personalizzare il formato del messaggio se necessario
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