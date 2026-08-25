import asyncio
import logging
from redis.asyncio import Redis
from jobs.models import WorkerHeartbeat, WorkerStatus

logger = logging.getLogger(__name__)

# Lua script to renew lock only if the worker still owns it
RENEW_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("expire", KEYS[1], ARGV[2])
else
    return 0
end
"""

# Lua script to delete lock only if the worker still owns it
RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

class WorkerLease:
    def __init__(self, redis_client: Redis, worker_id: str, lock_ttl: int = 30):
        self.redis = redis_client
        self.worker_id = worker_id
        self.lock_ttl = lock_ttl
        self.lock_key = "locks:microsoft_worker"
        self.heartbeat_key = f"workers:{worker_id}"
        
        # Register scripts
        self._renew_script = self.redis.register_script(RENEW_SCRIPT)
        self._release_script = self.redis.register_script(RELEASE_SCRIPT)

    async def acquire_lock(self) -> bool:
        """Tries to acquire the global worker lock."""
        acquired = await self.redis.set(
            self.lock_key, self.worker_id, nx=True, ex=self.lock_ttl
        )
        return bool(acquired)

    async def start_heartbeat(self):
        """Background task to continuously renew lock and update heartbeat state."""
        logger.info(f"[{self.worker_id}] Starting heartbeat loop...")
        while True:
            try:
                # Renew lock
                renewed = await self._renew_script(
                    keys=[self.lock_key], args=[self.worker_id, self.lock_ttl]
                )
                if not renewed:
                    logger.warning(f"[{self.worker_id}] Failed to renew lock! Lost ownership.")
                
                # Update heartbeat
                hb = WorkerHeartbeat(worker_id=self.worker_id, status=WorkerStatus.BUSY)
                await self.redis.set(self.heartbeat_key, hb.model_dump_json(), ex=self.lock_ttl * 2)
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
            
            # Sleep for a fraction of TTL to ensure timely renewal
            await asyncio.sleep(self.lock_ttl / 3)
            
    async def release_lock(self):
        """Releases the lock if this worker owns it."""
        try:
            await self._release_script(keys=[self.lock_key], args=[self.worker_id])
            await self.redis.delete(self.heartbeat_key)
            logger.info(f"[{self.worker_id}] Released lock and cleaned up heartbeat.")
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
