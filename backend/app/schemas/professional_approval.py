from pydantic import BaseModel, Field


class ProfessionalRejectionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)