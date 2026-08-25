import logging
import redis
import os

class RedisListHandler(logging.Handler):
    def __init__(self, redis_url="redis://localhost:6379/0", key="worker:logs", max_logs=200):
        super().__init__()
        self.redis_client = redis.from_url(redis_url)
        self.key = key
        self.max_logs = max_logs

    def emit(self, record):
        try:
            log_entry = self.format(record)
            self.redis_client.lpush(self.key, log_entry)
            self.redis_client.ltrim(self.key, 0, self.max_logs - 1)
        except Exception:
            pass

def setup_redis_logging():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    handler = RedisListHandler(redis_url=redis_url)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    # To avoid duplicate logs in the console if there's already a StreamHandler, we just add ours
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
