import asyncio
import logging
import os
from redis.asyncio import Redis

from jobs.consumer import JobConsumer
from jobs.lock import WorkerLease
from diagnostics.logger import setup_redis_logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    setup_redis_logging()
    logger.info("Starting GETCID Microsoft Operation Worker...")
    
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    import uuid
    # Always generate a unique worker ID to bypass any zombie locks from Portainer
    worker_id = f"worker_{uuid.uuid4().hex[:6]}"
    
    redis_client = Redis.from_url(redis_url)
    lease = WorkerLease(redis_client=redis_client, worker_id=worker_id)
    
    # Start heartbeat task in background
    heartbeat_task = asyncio.create_task(lease.start_heartbeat())
    
    consumer = JobConsumer(lease=lease)
    
    try:
        await consumer.consume_loop()
    except asyncio.CancelledError:
        logger.info("Worker shutdown requested.")
    finally:
        heartbeat_task.cancel()
        await lease.release_lock()
        logger.info("Worker shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
