from fastapi import APIRouter, Header, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Literal, Optional
from models import StandardErrorResponse
import os
import hmac
from itgs import Itgs
import asyncio

router = APIRouter()


class UpdateArgs(BaseModel):
    repo: Literal["backend", "websocket", "frontend", "jobs"] = Field(
        description="the repository identifier that was updated",
    )


ERROR_401_TYPE = Literal["not_set", "bad_format"]
ERROR_403_TYPE = Literal["invalid"]


@router.post(
    "/update",
    status_code=202,
    responses={
        "401": {
            "description": "if authorization is not set",
            "model": StandardErrorResponse[ERROR_401_TYPE],
        },
        "403": {
            "description": "if the authorization is invalid",
            "model": StandardErrorResponse[ERROR_403_TYPE],
        },
    },
)
async def update(args: UpdateArgs, authorization: Optional[str] = Header(None)):
    """Triggers deployment of the latest version of the given repository.
    Authorization must be of the form 'token <token>' where token is the shared
    deployment secret
    """
    if authorization is None:
        return JSONResponse(
            content=StandardErrorResponse[ERROR_401_TYPE](
                type="not_set", message="authorization header not set"
            ).dict(),
            status_code=401,
        )
    if not authorization.startswith("token "):
        return JSONResponse(
            content=StandardErrorResponse[ERROR_401_TYPE](
                type="bad_format",
                message="authorization header should start with 'token '",
            ).dict(),
            status_code=401,
        )
    token = authorization[len("token ") :]
    if not hmac.compare_digest(token, os.environ["DEPLOYMENT_SECRET"]):
        return JSONResponse(
            content=StandardErrorResponse[ERROR_403_TYPE](
                type="invalid",
                message="token is invalid",
            ).dict(),
            status_code=403,
        )

    async with Itgs() as itgs:
        redis = await itgs.redis()
        await redis.publish(f"updates:{args.repo}", "1")

    return Response(status_code=202)
