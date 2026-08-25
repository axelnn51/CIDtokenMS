import os
import sys
import uuid
import time
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import redis.asyncio as redis

# Reusing worker models for simplicity (in a real monorepo they might be in a shared package)
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "worker"))
from jobs.models import Job, JobPayload, JobStatus

app = FastAPI(title="GETCID API")

# Serve the beautiful frontend
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "frontend")), name="static")

@app.get("/")
async def root_ui():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"))

@app.get("/index.css")
async def css():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.css"))

@app.get("/app.js")
async def js():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "frontend", "app.js"))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL)

class GetTokenRequest(BaseModel):
    target_url: str = "https://my.visualstudio.com/"

class GetTokenResponse(BaseModel):
    job_id: str
    status: str

@app.on_event("startup")
async def startup_event():
    # Ping Redis to ensure connection
    await redis_client.ping()

@app.post("/api/v1/get-token", status_code=status.HTTP_202_ACCEPTED, response_model=GetTokenResponse)
async def create_job(request: GetTokenRequest):
    job_id = f"token_req_{uuid.uuid4().hex[:8]}"
    
    # Create the job object
    job = Job(
        job_id=job_id,
        payload=JobPayload(target_url=request.target_url)
    )
    
    # Save job data
    data_key = f"jobs:data:{job_id}"
    await redis_client.set(data_key, job.model_dump_json())
    
    # Push to stream
    await redis_client.xadd("jobs:stream", {"job_id": job_id})
    
    return GetTokenResponse(job_id=job_id, status=JobStatus.PENDING.value)

@app.get("/api/v1/jobs/{job_id}")
async def get_job_status(job_id: str):
    data_key = f"jobs:data:{job_id}"
    raw_data = await redis_client.get(data_key)
    
    if not raw_data:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = Job.model_validate_json(raw_data)
    
    if job.status == JobStatus.COMPLETED:
        return {
            "job_id": job.job_id,
            "status": job.status,
            "result": job.result.model_dump(exclude_none=True)
        }
    else:
        return {
            "job_id": job.job_id,
            "status": job.status
        }

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/v1/logs")
async def get_worker_logs(limit: int = 50):
    """
    Fetch the latest logs from the worker(s) directly from Redis.
    """
    logs = await redis_client.lrange("worker:logs", 0, limit - 1)
    return {"logs": [log.decode("utf-8") for log in logs]}
