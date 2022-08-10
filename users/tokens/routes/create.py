from typing import Optional
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from models import STANDARD_ERRORS_BY_CODE, StandardErrorResponse

router = APIRouter()


class CreateUserTokenRequest(BaseModel):
    name: str = Field(
        description="The desired human-readable name for identifying this",
    )
    expires_at: Optional[float] = Field(
        None,
        title="Expires at",
        description="When the token will expire in seconds since the unix epoch",
    )


class CreateUserTokenResponse(BaseModel):
    uid: str = Field(description="The primary stable idenitifier for this token")
    token: str = Field(description="The shared secret to use to identify in the future")
    name: str = Field(description="The human-readable name for identifying this")
    created_at: float = Field(
        name="Created at",
        description="When the token was created in seconds since the unix epoch",
    )
    expires_at: Optional[float] = Field(
        None,
        name="Expires at",
        description="When the token will expire in seconds since the unix epoch",
    )


@router.post(
    "/", response_model=CreateUserTokenResponse, responses=STANDARD_ERRORS_BY_CODE
)
async def create_user_token(
    args: CreateUserTokenRequest, authorization: Optional[str] = Header(None)
):
    pass
