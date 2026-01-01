from aio_pika import connect_robust, IncomingMessage
from database import AsyncSessionLocal
import json
import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool
from analyzer import IntelligentAnalyzer
from contexts import RuleAnalysisContext
from models import Alert
from datetime import datetime, timezone

class RabbitMQIntelligentConsumer:
    def __init__(self, rabbitmq_url: str, queue_name: str, analyzer: IntelligentAnalyzer, redis_url: str, redis_max_connections: int = 20):
        self.rabbitmq_url = rabbitmq_url
        self.queue_name = queue_name
        self.redis_url = redis_url
        self.redis_max_connections = redis_max_connections
        self.connection = None
        self.channel = None
        self.queue = None
        self.redis = None
        self.analyzer = analyzer

    async def connect(self):
        self.connection = await connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()

        await self.channel.set_qos(prefetch_count=10)

        self.queue = await self.channel.declare_queue(self.queue_name, durable=True)
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
                        # Scrivi su coda e salva nel DB
                        for alert in alerts:
                            db.add(Alert(
                                sensor_type=alert['sensor_type'],
                                message=alert['message'],
                                timestamp=datetime.now(timezone.utc),
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


                except Exception as e:
                    print(f"Errore nel processing del messaggio: {e}")
                    raise e
    
    async def close(self):
        if self.redis:
            await self.redis.close()
        if self.connection:
            await self.connection.close()