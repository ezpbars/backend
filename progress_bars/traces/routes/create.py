from models import STANDARD_ERRORS_BY_CODE, StandardErrorResponse
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, validator
from resources.uids import is_safe_uid
from fastapi import APIRouter, Header
from typing import Literal, Optional
from auth import auth_any
from itgs import Itgs
import time

router = APIRouter()


class CreateProgressBarTraceRequest(BaseModel):
    pbar_name: str = Field(
        description="the human-readable name for identifying the progress bar the trace is for",
        min_length=1,
        max_length=255,
    )
    uid: str = Field(
        description="the primary stable identifyer for this progress bar trace"
    )
    step_name: str = Field(
        description=(
            "the name of the first step in the trace; if this doesn't match the progress bar,"
            " the version of the progress bar will be incremented, and the old traces are discarded"
        )
    )
    iterations: Optional[int] = Field(
        description="the number of iterations in the starting step for this trace, none if the step is one-off",
        ge=1,
    )
    now: float = Field(
        description="the current time in seconds since the epoch; improves consistency",
    )

    @validator("uid")
    def uid_must_be_safe(cls, uid):
        if not is_safe_uid(uid):
            raise ValueError("uid must be url safe")
        return uid


ERROR_409_TYPE = Literal["uid_taken"]
"""the error type for a 409 response"""


@router.post(
    "/",
    status_code=204,
    responses={
        "409": {
            "description": "uid is already taken",
            "model": StandardErrorResponse[ERROR_409_TYPE],
        },
        **STANDARD_ERRORS_BY_CODE,
    },
)
async def create_trace(
    args: CreateProgressBarTraceRequest, authorization: Optional[str] = Header(None)
):
    """starts a new trace

    your endpoint should decide on a uid and return it to the client without
    blocking on the response from this endpoint. However, if there is a queueing
    period before the thing the progress bar is tracking is actually done,
    it's strongly suggested that you call the first step something like
    "assigning a server" and call this endpoint prior to queueing the job (but
    after responding to the client).)

    This accepts cognito or user token authentication. You can read more about
    the forms of authentication at [/rest_auth.html](/rest_auth.html)"""
    async with Itgs() as itgs:
        auth_result = await auth_any(itgs, authorization)
        if not auth_result.success:
            return auth_result.error_response
        conn = await itgs.conn()
        cursor = conn.cursor()
        response = await cursor.execute(
            "SELECT 1 FROM progress_bar_traces WHERE uid = ?", (args.uid,)
        )
        if response.results:
            return JSONResponse(
                content=StandardErrorResponse[ERROR_409_TYPE](
                    type="uid_taken",
                    message="that uid is already taken",
                ).dict(),
                status_code=409,
            )
        redis = await itgs.redis()
        now = time.time()
        if abs(now - args.now) < 300:
            now = args.now
        async with redis.pipeline(True) as pipe:
            await pipe.hmset(
                f"trace:{auth_result.result.sub}:{args.pbar_name}:{args.uid}",
                {
                    "created_at": now,
                    "last_updated_at": now,
                    "current_step": 1,
                    "done": "0",
                },
            )
            await pipe.hmset(
                f"trace:{auth_result.result.sub}:{args.pbar_name}:{args.uid}:step:1",
                {
                    "step_name": args.step_name,
                    "iteration": 0,
                    "iterations": args.iterations or 0,
                    "started_at": now,
                },
            )
            await pipe.execute()
        await redis.publish(
            f"ps:trace:{auth_result.result.sub}:{args.pbar_name}:{args.uid}", "created"
        )
        return Response(status_code=204)
