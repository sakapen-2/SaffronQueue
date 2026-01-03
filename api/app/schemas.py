from pydantic import BaseModel, Field

class JobCreate(BaseModel):
    payload: str = Field(min_length=1, max_length=50_000)
    max_attempts: int = Field(default=5, ge=1, le=20)

class JobOut(BaseModel):
    id: str
    status: str
    payload: str
    result: str | None = None
    attempts: int
    max_attempts: int
    last_error: str | None = None
