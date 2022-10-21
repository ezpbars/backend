from models import STANDARD_ERRORS_BY_CODE, StandardErrorResponse
from fastapi.responses import JSONResponse, Response
from redis.asyncio.client import Pipeline
from pydantic import BaseModel, Field, validator
from fastapi import APIRouter, Header
from typing import List, Literal, Optional, Tuple
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

    @validator("done")
    def done_must_be_true_if_iteration_is_iterations(cls, done, values: dict):
        if done and values.get("iteration") != values.get("iterations"):
            raise ValueError("done must be false if iteration is not iterations")
        return done


ERROR_404_TYPE = Literal["trace_not_found"]
"""the error type for a 404 response"""
ERROR_409_TYPE = Literal[
    "trace_completed", "missing_start_time", "step_changed", "backwards_progress"
]


@router.post(
    "/",
    responses={
        "404": {
            "description": "there is no in progress trace with that uid for that progress bar",
            "model": StandardErrorResponse[ERROR_404_TYPE],
        },
        "409": {
            "description": "the specified step is incompatible with the current state of the trace",
            "model": StandardErrorResponse[ERROR_409_TYPE],
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

        async def try_update_trace(pipe: Pipeline) -> Tuple[bool, Optional[Response]]:
            result: List[bytes] = await pipe.hmget(
                trace_key,
                ["current_step", "done"],
            )
            if result[0] is None:
                return False, JSONResponse(
                    StandardErrorResponse[ERROR_404_TYPE](
                        type="trace_not_found",
                        message="there is no in progress trace with that uid for that progress bar",
                    ).dict(),
                    status_code=404,
                )
            if result[1] == b"1":
                return False, JSONResponse(
                    StandardErrorResponse[ERROR_409_TYPE](
                        type="trace_completed",
                        message="the specified step is incompatible with the current state of the trace",
                    ).dict(),
                    status_code=409,
                )
            current_step = int(result[0])
            current_step_key = f"trace:{auth_result.result.sub}:{args.pbar_name}:{args.trace_uid}:step:{current_step}"
            next_step_key = f"trace:{auth_result.result.sub}:{args.pbar_name}:{args.trace_uid}:step:{current_step + 1}"
            result = await pipe.hmget(
                current_step_key,
                ["step_name", "iteration", "iterations"],
            )
            if result[0] is None:
                return False, JSONResponse(
                    {
                        "message": "integrity error: the trace exists but not its current step"
                    },
                    headers={"retry-after": "5"},
                    status_code=503,
                )
            step_name: str = result[0].decode("utf-8")
            iterations: Optional[int] = int(result[2]) if result[2] != b"0" else None
            iteration: Optional[int] = (
                int(result[1]) if iterations is not None else None
            )
            if step_name != args.step_name:
                if args.done or args.iteration is not None and args.iteration != 0:
                    return False, JSONResponse(
                        StandardErrorResponse[ERROR_409_TYPE](
                            type="missing_start_time",
                            message=(
                                "attempting to start a new step but the new step is not in its initial state,"
                                " i.e., either done is true, or the step is iterated and not at its first iteration;"
                                " this means we don't know when this new step started, which is critical for statistics"
                            ),
                        ).dict(),
                        status_code=409,
                    )
                pipe.multi()
                if iterations is not None:
                    await pipe.hset(current_step_key, "iteration", iterations)
                await pipe.hset(current_step_key, "finished_at", now)
                await pipe.hset(
                    trace_key,
                    mapping={
                        "last_updated_at": now,
                        "current_step": current_step + 1,
                    },
                )
                await pipe.hset(
                    next_step_key,
                    mapping={
                        "step_name": args.step_name,
                        "started_at": now,
                        "iteration": 0,
                        "iterations": args.iterations
                        if args.iterations is not None
                        else 0,
                    },
                )
                for key in [current_step_key, trace_key, next_step_key]:
                    await pipe.expire(key, 86400)
                return True, None

            if args.iterations != iterations:
                return False, JSONResponse(
                    StandardErrorResponse[ERROR_409_TYPE](
                        type="step_changed",
                        message=(
                            "you provided new information on the same step in the same trace,"
                            " but it either was iterated and is no longer iterated, or was not"
                            " iterated and is now iterated - you need to be consistent"
                        ),
                    ).dict(),
                    status_code=409,
                )
            if iterations is not None and args.iteration < iteration:
                return False, JSONResponse(
                    StandardErrorResponse[ERROR_409_TYPE](
                        type="backwards_progress",
                        message=(
                            "you provided new information on the same step in the same trace,"
                            " but it was iterated and the iteration is less than the previous iteration"
                        ),
                    ).dict(),
                    status_code=409,
                )

            if args.done:
                assert args.iteration == iterations
                pipe.multi()
                await pipe.hset(
                    current_step_key,
                    mapping={
                        "iteration": iterations if iterations is not None else 0,
                        "finished_at": now,
                    },
                )
                await pipe.hset(
                    trace_key,
                    mapping={
                        "last_updated_at": now,
                        "done": 1,
                    },
                )
                for key in [current_step_key, trace_key]:
                    await pipe.expire(key, 86400)
                return True, None

            pipe.multi()
            await pipe.hset(trace_key, "last_updated_at", now)
            if args.iteration is not None and args.iteration != iteration:
                await pipe.hset(current_step_key, "iteration", args.iteration)
            for key in [trace_key, current_step_key]:
                await pipe.expire(key, 86400)
            return True, None

        result: Tuple[bool, Optional[Response]] = await redis.transaction(
            try_update_trace, trace_key, value_from_callable=True
        )
        if not result[0]:
            return result[1]
        await redis.publish(
            f"ps:trace:{auth_result.result.sub}:{args.pbar_name}:{args.trace_uid}",
            "updated trace",
        )
        if args.done:
            jobs = await itgs.jobs()
            await jobs.enqueue(
                "runners.handle_completed_trace",
                user_sub=auth_result.result.sub,
                pbar_name=args.pbar_name,
                trace_uid=args.trace_uid,
            )
        return Response(status_code=204)
