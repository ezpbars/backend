from pickle import TRUE
from models import STANDARD_ERRORS_BY_CODE, StandardErrorResponse
from fastapi.responses import JSONResponse, Response
from redis.asyncio.client import Pipeline
from pydantic import BaseModel, Field, validator
from fastapi import APIRouter, Header
from typing import List, Literal, Optional
from auth import auth_any
from itgs import Itgs
import time

router = APIRouter()


class CreateProgressBarTraceStepRequest(BaseModel):
    pbar_name: str = Field(
        description="The name of the progress bar the trace belongs to"
    )
    trace_uid: str = Field(
        description="The unique identifier of the trace the step belongs to"
    )
    step_name: str = Field(description="The name of the trace the step belongs to")
    iteration: Optional[int] = Field(
        description="if the step is one-off, none, otherwise, the number of completed iterations so far in this steps",
        ge=0,
    )
    iterations: Optional[int] = Field(
        description="The total number of iterations this step has, if it is iterated",
        ge=1,
    )
    done: bool = Field(
        description="Whether or not the entire trace is done, i.e., this is the last step, and this step is done"
    )
    now: float = Field(
        description="the current time in seconds since the epoch; improves consistency",
    )

    @validator("iterations")
    def iterations_must_be_greater_than_iteration(cls, iterations, values: dict):
        if iterations is not None and values.get("iteration") is None:
            raise ValueError("iterations must be none if iteration is none")
        if iterations is not None and iterations < values.get("iteration"):
            raise ValueError("iterations must be greater than or equal to iteration")
        return iterations


ERROR_404_TYPE = Literal["trace_not_found"]
"""the error type for a 404 response"""


@router.post(
    "/",
    responses={
        "404": {
            "description": "there is no in progress trace with that uid for that progress bar",
            "model": StandardErrorResponse[ERROR_404_TYPE],
        },
        **STANDARD_ERRORS_BY_CODE,
    },
    status_code=204,
)
async def create_progress_bar_trace_step(
    args: CreateProgressBarTraceStepRequest, authorization: Optional[str] = Header(None)
):
    """Create a new step in an in progress progress bar trace
    Note: any progress bar trace returned by the search endpoint is definitely
    not in progress. This refers to traces created by the create trace endpoint
    before this endpoint has been called with done set to true

    This accepts cognito or user token authentication. You can read more about
    the forms of authentication at [/rest_auth.html](/rest_auth.html)
    """
    async with Itgs() as itgs:
        auth_result = await auth_any(itgs, authorization)
        if not auth_result.success:
            return auth_result.error_response
        now = time.time()
        if (now - args.now) < 300:
            now = args.now
        redis = await itgs.redis()
        trace_key = f"trace:{auth_result.result.sub}:{args.pbar_name}:{args.trace_uid}"

        async def try_update_trace(pipe: Pipeline) -> bool:
            result: List[bytes] = await pipe.hmget(
                trace_key,
                ["current_step", "done"],
            )
            if result[0] is None:
                return False
            if result[1] == b"1":
                return False
            current_step = int(result[0])
            current_step_key = f"trace:{auth_result.result.sub}:{args.pbar_name}:{args.trace_uid}:step:{current_step}"
            next_step_key = f"trace:{auth_result.result.sub}:{args.pbar_name}:{args.trace_uid}:step:{current_step + 1}"
            result = await pipe.hmget(
                current_step_key,
                ["step_name", "iteration", "iterations"],
            )
            if result[0] is None:
                return False
            step_name: str = result[0].decode("utf-8")
            iterations: Optional[int] = int(result[2]) if result[2] != b"0" else None
            iteration: Optional[int] = (
                int(result[1]) if iterations is not None else None
            )
            if step_name != args.step_name:
                if args.done or args.iteration is not None and args.iteration != 0:
                    return False  # we're missing when the step started
                if iterations is not None:
                    await pipe.hset(current_step_key, "iteration", iterations)
                await pipe.hset(current_step_key, "finished_at", now)
                await pipe.hmset(
                    trace_key,
                    {
                        "last_updated_at": now,
                        "current_step": current_step + 1,
                    },
                )
                await pipe.hmset(
                    next_step_key,
                    {
                        "step_name": args.step_name,
                        "started_at": now,
                        "iteration": 0,
                        "iterations": args.iterations
                        if args.iterations is not None
                        else 0,
                    },
                )
                return True

            if args.iterations != iterations:
                return False
            if iterations is not None and args.iteration < iteration:
                return False

            if args.done:
                if args.iteration != iterations:
                    return False
                await pipe.hmset(
                    current_step_key,
                    {
                        "iteration": iterations if iterations is not None else 0,
                        "finished_at": now,
                    },
                )
                await pipe.hmset(
                    trace_key,
                    {
                        "last_updated_at": now,
                        "done": 1,
                    },
                )
                return True

            await pipe.hset(trace_key, "last_updated_at", now)
            if args.iteration is not None and args.iteration != iteration:
                await pipe.hset(current_step_key, "iteration", args.iteration)
            return True

        result = await redis.transaction(
            try_update_trace, trace_key, value_from_callable=True
        )
        if not result:
            return JSONResponse(
                StandardErrorResponse[ERROR_404_TYPE](
                    type="trace_not_found",
                    message="there is no in progress trace with that uid for that progress bar",
                ).dict(),
                status_code=404,
            )
        await redis.publish(
            f"ps:trace:{auth_result.result.sub}:{args.pbar_name}:{args.trace_uid}",
            "updated trace",
        )
        return Response(status_code=204)
