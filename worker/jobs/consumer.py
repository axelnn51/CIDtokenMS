import asyncio
import logging
from redis.asyncio import Redis
from jobs.lock import WorkerLease
from jobs.state_manager import JobStateManager
from jobs.models import JobStatus, JobResult
from browser.lifecycle import BrowserLifecycle
from microsoft.authentication import MicrosoftAuthenticator
from microsoft.operation import MicrosoftOperation

logger = logging.getLogger(__name__)

class JobConsumer:
    def __init__(self, lease: WorkerLease, redis_client: Redis = None):
        self.lease = lease
        self.redis = redis_client or lease.redis
        self.state_manager = JobStateManager(self.redis)
        self.stream_key = "jobs:stream"
        self.group_name = "worker_group"
        self.consumer_name = lease.worker_id
        self._is_running = False

    async def _ensure_group(self):
        try:
            await self.redis.xgroup_create(self.stream_key, self.group_name, id="0", mkstream=True)
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                logger.error(f"Error creating group: {e}")

    async def consume_loop(self):
        self._is_running = True
        await self._ensure_group()
        
        logger.info(f"[{self.consumer_name}] Waiting for jobs...")
        
        while self._is_running:
            if not await self.lease.acquire_lock():
                await asyncio.sleep(2)
                continue
                
            try:
                messages = await self.redis.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={self.stream_key: ">"},
                    count=1,
                    block=5000
                )
                
                if messages:
                    for stream, msgs in messages:
                        for msg_id, data in msgs:
                            job_id = data.get(b"job_id").decode("utf-8")
                            await self._process_job(job_id, msg_id)
            except Exception as e:
                logger.error(f"Consumer loop error: {e}")
                await asyncio.sleep(2)

    async def _process_job(self, job_id: str, msg_id: bytes):
        logger.info(f"[{self.consumer_name}] Processing Job: {job_id}")
        
        try:
            job = await self.state_manager.get_job(job_id)
        except Exception as e:
            logger.error(f"Could not load job {job_id}: {e}")
            await self.redis.xack(self.stream_key, self.group_name, msg_id)
            return

        # Guarantee cleanup using try...finally for both Browser and Redis Lock
        try:
            await self.state_manager.update_state(job, JobStatus.STARTING_BROWSER)
            
            # The async with guarantees that Chromium will close properly
            async with BrowserLifecycle() as context:
                
                # Check Auth
                await self.state_manager.update_state(job, JobStatus.AUTHENTICATING)
                authenticator = MicrosoftAuthenticator(context)
                auth_status = await authenticator.check_auth_status()
                
                if auth_status != JobStatus.EXECUTING:
                    # e.g., CHALLENGE_REQUIRED
                    await self.state_manager.update_state(job, auth_status, result=JobResult(error_message="Manual intervention required."))
                    # If we don't ACK, it stays in PENDING/PEL. Adjust based on how you want to handle challenges.
                    # For now, we'll ACK and let the human fix the profile outside this job, or implement a pause.
                    await self.redis.xack(self.stream_key, self.group_name, msg_id)
                    return
                
                # Execute Operation
                await self.state_manager.update_state(job, JobStatus.EXECUTING)
                operation = MicrosoftOperation(context)
                
                result = await operation.execute_getcid(job.payload.installation_id)
                
                if result.error_type:
                    await self.state_manager.update_state(job, JobStatus.FAILED_PERMANENTLY, result=result)
                else:
                    await self.state_manager.update_state(job, JobStatus.COMPLETED, result=result)
                
                # ACK only after successful logic
                await self.redis.xack(self.stream_key, self.group_name, msg_id)
                logger.info(f"[{self.consumer_name}] Job {job_id} Processed and ACKed.")
                
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            await self.state_manager.update_state(job, JobStatus.FAILED_PERMANENTLY, result=JobResult(error_message=str(e)))
            await self.redis.xack(self.stream_key, self.group_name, msg_id)
        finally:
            await self.lease.release_lock()
