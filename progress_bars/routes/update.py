from typing import Literal, Optional
from fastapi import APIRouter, Header
from fastapi.responses import Response, JSONResponse
from auth import auth_any
from itgs import Itgs
from models import STANDARD_ERRORS_BY_CODE, StandardErrorResponse
from pydantic import BaseModel, Field

from progress_bars.steps.routes.create import (
    CreateProgressBarStepRequestItem,
    CreateProgressBarStepResponseItem,
)
from progress_bars.steps.routes.update import UpdateProgressBarStepResponseItem

router = APIRouter()

ERROR_404_TYPE = Literal["not_found"]
"""the error type for a 404 response"""


class UpdateProgressBarRequest(BaseModel):
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
    default_step_config: CreateProgressBarStepRequestItem = Field(
        default_factory=lambda: CreateProgressBarStepRequestItem(),
        description="the configuration to use for steps by default",
    )


class UpdateProgressBarResponse(BaseModel):
    sampling_max_count: int = Field(
        description="the maximum number of samples to retain for prediction for this progress bar",
    )
    sampling_max_age_seconds: int = Field(
        description="the maximum age of samples to retain for prediction"
    )
    sampling_technique: str = Field(
        description="the technique to use when selecting samples to be used for prediction"
    )
    default_step_config: UpdateProgressBarStepResponseItem = Field(
        description="the default configuration used for steps"
    )


@router.put(
    "/",
    response_model=UpdateProgressBarResponse,
    status_code=200,
    responses={
        "404": {
            "description": "conflict - too many unexpired user tokens",
            "model": StandardErrorResponse[ERROR_404_TYPE],
        },
        **STANDARD_ERRORS_BY_CODE,
    },
)
async def update_progress_bar(
    name: str,
    args: UpdateProgressBarRequest,
    authorization: Optional[str] = Header(None),
):
    """updates the settings of the progress bar with the given name, only works
    if the progress bar is owned by you.

    This accepts cognito or user token authentication. You can read more about the
    forms of authentication at [/rest_auth.html](/rest_auth.html)"""
    async with Itgs() as itgs:
        auth_result = await auth_any(itgs, authorization)
        if not auth_result.success:
            return auth_result.error_response
        conn = await itgs.conn()
        cursor = conn.cursor("none")
        response = await cursor.executemany3(
            (
                """
                UPDATE progress_bars
                SET
                    sampling_max_count = ?,
                    sampling_max_age_seconds = ?,
                    sampling_technique = ?
                WHERE
                    progress_bars.name = ?
                    AND EXISTS (
                        SELECT 1 FROM users
                        WHERE users.id = progress_bars.user_id
                        AND users.sub = ?
                    )
                """,
                (
                    args.sampling_max_count,
                    args.sampling_max_age_seconds,
                    args.sampling_technique,
                    name,
                    auth_result.result.sub,
                ),
            ),
            (
                """
                UPDATE progress_bar_steps
                SET
                    one_off_technique = ?,
                    one_off_percentile = ?,
                    iterated_technique = ?,
                    iterated_percentile = ?
                WHERE 
                    EXISTS (
                        SELECT 1 FROM progress_bars
                        WHERE progress_bars.id = progress_bar_steps.progress_bar_id
                            AND EXISTS (
                                SELECT 1 FROM users
                                WHERE users.id = user_tokens.user_id
                                  AND users.sub = ?
                            )
                            AND progress_bars.name = ?
                    )
                    AND progress_bar_steps.name = ?
                """,
                (
                    args.default_step_config.one_off_technique,
                    args.default_step_config.one_off_percentile,
                    args.default_step_config.iterated_technique,
                    args.default_step_config.iterated_percentile,
                    auth_result.result.sub,
                    name,
                    "default",
                ),
            ),
        )
        if (
            response.items[0].rows_affected is not None
            and response.items[0].rows_affected > 0
        ):
            return JSONResponse(
                content=UpdateProgressBarResponse(
                    sampling_max_count=args.sampling_max_count,
                    sampling_max_age_seconds=args.sampling_max_age_seconds,
                    sampling_technique=args.sampling_technique,
                    default_step_config=UpdateProgressBarStepResponseItem(
                        one_off_technique=args.default_step_config.one_off_technique,
                        one_off_percentile=args.default_step_config.one_off_percentile,
                        iterated_technique=args.default_step_config.iterated_technique,
                        iterated_percentile=args.default_step_config.iterated_percentile,
                    ),
                ).dict(),
                status_code=200,
            )
        return JSONResponse(
            content=StandardErrorResponse[ERROR_404_TYPE](
                type="not_found", message="progress bar with that name not found"
            ).dict(),
            status_code=404,
        )
