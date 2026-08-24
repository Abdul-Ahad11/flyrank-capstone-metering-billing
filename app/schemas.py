from pydantic import BaseModel

class GenerateRequest(BaseModel):
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0

class UsageDetail(BaseModel):
    used: int
    limit: int
    cost: int

class UsageResponse(BaseModel):
    api_calls: UsageDetail
    ai_tokens: UsageDetail