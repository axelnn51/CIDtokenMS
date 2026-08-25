import logging
import time
from redis.asyncio import Redis
from jobs.models import Job, JobStatus, JobResult

logger = logging.getLogger(__name__)

class JobStateManager:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.data_key_prefix = "jobs:data:"

    def _get_key(self, job_id: str) -> str:
        return f"{self.data_key_prefix}{job_id}"

    async def get_job(self, job_id: str) -> Job:
        key = self._get_key(job_id)
        raw_data = await self.redis.get(key)
        if not raw_data:
            raise ValueError(f"Job {job_id} not found")
        return Job.model_validate_json(raw_data)

    async def update_state(self, job: Job, new_status: JobStatus, result: JobResult = None):
        """Transitions job to a new state and updates Redis."""
        old_status = job.status
        job.status = new_status
        
        if new_status == JobStatus.STARTING_BROWSER and old_status == JobStatus.PENDING:
            job.metrics.started_at = time.time()
            
        if new_status in [JobStatus.COMPLETED, JobStatus.FAILED_PERMANENTLY, JobStatus.TIMEOUT, JobStatus.CANCELLED]:
            job.metrics.completed_at = time.time()
            
        if result:
            job.result = result
            
        key = self._get_key(job.job_id)
        # Store updated job. Give it a 24-hour TTL when completed to not clog Redis
        ttl = 86400 if new_status in [JobStatus.COMPLETED, JobStatus.FAILED_PERMANENTLY, JobStatus.CANCELLED] else None
        
        if ttl:
            await self.redis.set(key, job.model_dump_json(), ex=ttl)
        else:
            await self.redis.set(key, job.model_dump_json())
            
        logger.info(f"[JOB {job.job_id}] State changed: {old_status} -> {new_status}")
