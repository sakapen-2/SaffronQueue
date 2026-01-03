from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str

    job_queue: str = "job_queue"
    job_processing: str = "job_processing"
    job_dlq: str = "job_dlq"
    job_delayed: str = "job_delayed"

    log_level: str = "INFO"

settings = Settings()
