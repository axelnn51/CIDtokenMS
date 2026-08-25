from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import time

class JobStatus(str, Enum):
    PENDING = "PENDING"
    STARTING_BROWSER = "STARTING_BROWSER"
    AUTHENTICATING = "AUTHENTICATING"
    CHALLENGE_REQUIRED = "CHALLENGE_REQUIRED"
    EXECUTING = "EXECUTING"
    VALIDATING_RESULT = "VALIDATING_RESULT"
    COMPLETED = "COMPLETED"
    RETRYABLE_ERROR = "RETRYABLE_ERROR"
    FAILED_PERMANENTLY = "FAILED_PERMANENTLY"
    UNKNOWN_STATE = "UNKNOWN_STATE"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"

class JobPayload(BaseModel):
    installation_id: str = Field(..., max_length=100)

class JobMetrics(BaseModel):
    created_at: float = Field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

class JobResult(BaseModel):
    cid: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None

class Job(BaseModel):
    job_id: str
    payload: JobPayload
    status: JobStatus = JobStatus.PENDING
    metrics: JobMetrics = Field(default_factory=JobMetrics)
    result: JobResult = Field(default_factory=JobResult)
    retry_count: int = 0
    
class WorkerStatus(str, Enum):
    IDLE = "IDLE"
    BUSY = "BUSY"

class WorkerHeartbeat(BaseModel):
    worker_id: str
    status: WorkerStatus = WorkerStatus.IDLE
    job_id: Optional[str] = None
    heartbeat: float = Field(default_factory=time.time)
