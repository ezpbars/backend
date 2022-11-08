import secrets
import time
from typing import Literal, Optional
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from auth import auth_any
from itgs import Itgs
from models import STANDARD_ERRORS_BY_CODE, StandardErrorResponse
from progress_bars.steps.routes.create import (
    CreateProgressBarStepRequest,
    CreateProgressBarStepResponse,
)

router = APIRouter()


class CreateProgressBarRequest(BaseModel):
    name: str = Field(
        description="the human-readable name for identifying this progress bar",
        min_length=1,
        max_length=255,
    )
    sampling_max_count: int = Field(
        100,
        description="the maximum number of samples to retain for prediction for this progress bar",
        ge=10,
    )
    sampling_max_age_seconds: Optional[int] = Field(
        604800, description="the maximum age of samples to retain for prediction", ge=60
    )
    sampling_technique: Literal["systematic", "simple_random"] = Field(
        "systematic",
        description="""one of `systematic`, or `simple_random` where:
  - `systematic`: selects and retains each trace unless a trace has already been
    retained within a minimum interval the intervals chosen such that the
    maximum number of samples taken over the maximum age (one week if not set)
    does not exceed the max count for this progress bar; for example, if the max
    count is ten, and the interval is five seconds, then this will retain at most
    one sample every two seconds. Tends to over sample low periods of activity,
    but has a hard limit on the number of traces retained.
  - `simple_random`: selects and retains each trace with equal probability. The
    probability is initialized to one and tends towards x/n where x is the max
    count and n is the number of traces over the previous rolling max age (one
    week if not set). Accurately samples but has no hard limit on the number of
    samples retained.""",
    )
    default_step_config: CreateProgressBarStepRequest = Field(
        default_factory=lambda: CreateProgressBarStepRequest(),
        description="the configuration to use for steps by default",
    )


class CreateProgressBarResponse(BaseModel):
    uid: str = Field(description="the primary stable identifyer for this progress bar")
    name: str = Field(
        description="the human-readable name for identifying this progress bar"
    )
    sampling_max_count: int = Field(
        description="the maximum number of samples to retain for prediction for this progress bar",
    )
    sampling_max_age_seconds: int = Field(
        description="the maximum age of samples to retain for prediction"
    )
    sampling_technique: str = Field(
        description="the technique to use when selecting samples to be used for prediction"
    )
    version: int = Field(
        description="the number of times the steps and traces had to be reset because we received a trace with different steps or it was updated via the api"
    )
    created_at: float = Field(
        description="when the progress bar was created in seconds since the unix epoch"
    )
    default_step_config: CreateProgressBarStepResponse = Field(
        description="the default configuration used for steps"
    )


ERROR_409_TYPE = Literal["progress_bar_name_already_exists"]
"""the error type for a 409 response"""


@router.post(
    "/",
    status_code=200,
    response_model=CreateProgressBarResponse,
    responses={
        "409": {
            "description": "conflict- a progress bar already exists with this name",
            "model": StandardErrorResponse[ERROR_409_TYPE],
        },
        **STANDARD_ERRORS_BY_CODE,
    },
)
async def create_progress_bar(
    args: CreateProgressBarRequest, authorization: Optional[str] = Header(None)
):
    """creates a new progress bar

    This accepts cognito or user token authentication. You can read more about the
    forms of authentication at [/rest_auth.html](/rest_auth.html)"""
    async with Itgs() as itgs:
        auth_result = await auth_any(itgs, authorization)
        if not auth_result.success:
            return auth_result.error_response
        now = time.time()
        pbar_uid = "ep_pb_" + secrets.token_urlsafe(8)
        step_uid = "ep_pbs_" + secrets.token_urlsafe(8)
        conn = await itgs.conn()
        cursor = conn.cursor("none")
        response = await cursor.executemany3(
            (
                (
                    """
                    INSERT INTO progress_bars (
                        user_id,
                        uid,
                        name,
                        sampling_max_count,
                        sampling_max_age_seconds,
                        sampling_technique,
                        version,
                        created_at
                    )
                    SELECT
                        users.id,
                        ?, ?, ?, ?, ?, ?, ?
                    FROM users
                    WHERE
                        users.sub = ?
                        AND NOT EXISTS (
                            SELECT 1 FROM progress_bars AS progress_bars_inner
                            WHERE
                              progress_bars_inner.user_id = users.id
                              AND progress_bars_inner.name = ?
                        )
                    """,
                    (
                        pbar_uid,
                        args.name,
                        args.sampling_max_count,
                        args.sampling_max_age_seconds,
                        args.sampling_technique,
                        0,
                        now,
                        auth_result.result.sub,
                        args.name,
                    ),
                ),
                (
                    """
                    INSERT INTO progress_bar_steps (
                        progress_bar_id,
                        uid,
                        name,
                        position,
                        iterated,
                        one_off_technique,
                        one_off_percentile,
                        iterated_technique,
                        iterated_percentile,
                        created_at
                    )
                    SELECT
                        progress_bars.id,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?
                    FROM progress_bars
                    WHERE
                        progress_bars.uid = ?
                    """,
                    (
                        step_uid,
                        "default",
                        0,
                        0,
                        args.default_step_config.one_off_technique,
                        args.default_step_config.one_off_percentile,
                        args.default_step_config.iterated_technique,
                        args.default_step_config.iterated_percentile,
                        now,
                        pbar_uid,
                    ),
                ),
            )
        )
        if (
            response.items[0].rows_affected is not None
            and response.items[0].rows_affected > 0
        ):
            return JSONResponse(
                content=CreateProgressBarResponse(
                    uid=pbar_uid,
                    name=args.name,
                    sampling_max_count=args.sampling_max_count,
                    sampling_max_age_seconds=args.sampling_max_age_seconds,
                    sampling_technique=args.sampling_technique,
                    version=0,
                    created_at=now,
                    default_step_config=CreateProgressBarStepResponse(
                        uid=step_uid,
                        name="default",
                        position=0,
                        iterated=False,
                        one_off_technique=args.default_step_config.one_off_technique,
                        one_off_percentile=args.default_step_config.one_off_percentile,
                        iterated_technique=args.default_step_config.iterated_technique,
                        iterated_percentile=args.default_step_config.iterated_percentile,
                        created_at=now,
                    ),
                ).dict(),
                status_code=201,
            )
        return JSONResponse(
            content=StandardErrorResponse[ERROR_409_TYPE](
                type="progress_bar_name_already_exists",
                message="a progress bar with that name already exists",
            ).dict(),
            status_code=409,
        )
