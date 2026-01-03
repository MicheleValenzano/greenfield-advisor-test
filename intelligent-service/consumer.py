from aio_pika import connect_robust, IncomingMessage, ExchangeType, Message
from database import AsyncSessionLocal
import json
import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool
from analyzer import IntelligentAnalyzer
from contexts import RuleAnalysisContext
from models import Alert
from datetime import datetime, timezone

ROUTING_KEY_PREFIX = "alerts."

class RabbitMQIntelligentConsumer:
    def __init__(self, rabbitmq_url: str, queue_name: str, alerts_exchange_name: str, analyzer: IntelligentAnalyzer, redis_url: str, redis_max_connections: int = 20):
        self.rabbitmq_url = rabbitmq_url
        self.queue_name = queue_name
        self.alerts_exchange_name = alerts_exchange_name
        self.redis_url = redis_url
        self.redis_max_connections = redis_max_connections
        self.connection = None
        self.channel = None
        self.queue = None
        self.redis = None
        self.alerts_exchange = None
        self.analyzer = analyzer

    async def connect(self):
        self.connection = await connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()

        await self.channel.set_qos(prefetch_count=10)

        self.queue = await self.channel.declare_queue(self.queue_name, durable=True)

        self.alerts_exchange = await self.channel.declare_exchange(self.alerts_exchange_name, ExchangeType.TOPIC, durable=True)

        await self.queue.consume(self.handle_message)

        try:
            pool = ConnectionPool.from_url(self.redis_url, max_connections=self.redis_max_connections)
            self.redis = aioredis.Redis(decode_responses=True, connection_pool=pool)
        except Exception:
            self.redis = None

    async def handle_message(self, message: IncomingMessage):
        async with message.process(requeue=True):
            async with AsyncSessionLocal() as db:
                try:
                    payload = json.loads(message.body.decode())

                    analysis_context = RuleAnalysisContext(
                        payload=payload,
                        db=db,
                        redis=self.redis
                    )
                    alerts = await self.analyzer.execute(analysis_context)
                    if alerts:
                        print(f"Alerts generated for payload {payload}: {alerts}")

                        now = datetime.now(timezone.utc)

                        # Scrivi su coda e salva nel DB
                        for alert in alerts:
                            alert['timestamp'] = now.isoformat()
                            db.add(Alert(
                                sensor_type=alert['sensor_type'],
                                message=alert['message'],
                                timestamp=now,
                                active=True,
                                field=alert['field'],
                                owner_id=alert['owner_id']
                            ))
                        try:
                            await db.commit()
                        except Exception as e:
                            await db.rollback()
                            print(f"Errore nel commit del DB: {e}")
                            raise e
                        
                        for alert in alerts:
                            routing_key = f"{ROUTING_KEY_PREFIX}{alert['field']}"

                            alert_message_body = json.dumps(alert).encode()
                            alert_message = Message(alert_message_body)
                            await self.alerts_exchange.publish(alert_message, routing_key=routing_key)

                            print(f"Alert pubbliacto su RabbitMQ con routing key {routing_key}: {alert}")


                except Exception as e:
                    print(f"Errore nel processing del messaggio: {e}")
                    raise e
    
    async def close(self):
        if self.redis:
            await self.redis.close()
        if self.connection:
            await self.connection.close()