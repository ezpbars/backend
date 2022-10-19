import secrets
import time
from typing import Literal, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse, Response
from auth import auth_any
from itgs import Itgs
from models import STANDARD_ERRORS_BY_CODE, StandardErrorResponse

router = APIRouter()


class CreateProgressBarStepRequest(BaseModel):
    iterated: bool = Field(
        False,
        description="""True if the step is iterated, i.e., it consists of
  many, identical, smaller steps, False for a one-off step, i.e., a step which is
  not repeated. Ignored for the default step""",
    )
    one_off_technique: Literal[
        "percentile", "harmonic_mean", "geometric_mean", "arithmetic_mean"
    ] = Field(
        "percentile",
        description="""required for non-iterated i.e., one-off
steps. The technique to use to predict the time step will take. one of the
following values:
- `percentile`: the fastest amount of time slower than a fixed percentage of
  the samples, see also: one_off_percentile
- `harmonic_mean`: the harmonic mean of the samples, https://en.wikipedia.org/wiki/Harmonic_mean
- `geometric_mean`: the geometric mean of the samples, https://en.wikipedia.org/wiki/Geometric_mean
- `arithmetic_mean`: the arithmetic mean of the samples, https://en.wikipedia.org/wiki/Arithmetic_mean""",
    )
    one_off_percentile: float = Field(
        75,
        description="""required for non-iterated steps using the
  percentile technique. the percent of samples which should complete faster than
  the predicted amount of time. for example, `25` means a quarter of samples
  complete before the progress bar reaches the end. Typically, a high value,
  such as 90, is chosen, since it's better to surprise the user with a faster
  result, than to annoy them with a slower result.""",
        ge=0,
        le=100,
    )
    iterated_technique: Literal[
        "best_fit.linear",
        "percentile",
        "harmonic_mean",
        "geometric_mean",
        "arithmetic_mean",
    ] = Field(
        "best_fit.linear",
        description="""required for iterated steps. The technique
  used to predict the time the step takes, unless otherwise noted, the technique
  is applied to the normalized speed, i.e., the speed divided by the number of
  iterations and the prediction is the predicted normalized speed multiplied by
  the number of iterations. Must be one of the following values:
  - `best_fit.linear`: fits the samples to t = mn+b where t is the predicted
    time, m is a variable, n is the number of iterations, and b is also a
    variable. This fit does not merely work on normalized speed.
  - `percentile`: see one_off_technique
  - `harmonic_mean`: see one_off_technique
  - `geometric_mean`: see one_off_technique
  - `arithmetic_mean`: see one_off_technique""",
    )
    iterated_percentile: float = Field(
        75, description="see one-off percentile", ge=0, le=100
    )


class CreateProgressBarStepResponse(BaseModel):
    uid: str = Field(description="the primary stable identifyer for this progress bar")
    name: str = Field(
        description="the human-readable name for identifying this progress bar"
    )
    position: int = Field(
        description="when the step occurs within the overall task, i.e., 1 is the first step. The default step has a position of 0",
    )
    iterated: bool = Field(
        description="""True if the step is iterated, i.e., it consists of
  many, identical, smaller steps, False for a one-off step, i.e., a step which is
  not repeated. Ignored for the default step"""
    )
    one_off_technique: Literal[
        "percentile", "harmonic_mean", "geometric_mean", "arithmetic_mean"
    ] = Field(
        "percentile",
        description="""required for non-iterated i.e., one-off
steps. The technique to use to predict the time step will take. one of the
following values:
- `percentile`: the fastest amount of time slower than a fixed percentage of
  the samples, see also: one_off_percentile
- `harmonic_mean`: the harmonic mean of the samples, https://en.wikipedia.org/wiki/Harmonic_mean
- `geometric_mean`: the geometric mean of the samples, https://en.wikipedia.org/wiki/Geometric_mean
- `arithmetic_mean`: the arithmetic mean of the samples, https://en.wikipedia.org/wiki/Arithmetic_mean""",
    )
    one_off_percentile: float = Field(
        description="""required for non-iterated steps using the
  percentile technique. the percent of samples which should complete faster than
  the predicted amount of time. for example, `25` means a quarter of samples
  complete before the progress bar reaches the end. Typically, a high value,
  such as 90, is chosen, since it's better to surprise the user with a faster
  result, than to annoy them with a slower result.""",
    )
    iterated_technique: Literal[
        "best_fit.linear",
        "percentile",
        "harmonic_mean",
        "geometric_mean",
        "arithmetic_mean",
    ] = Field(
        description="""required for iterated steps. The technique
  used to predict the time the step takes, unless otherwise noted, the technique
  is applied to the normalized speed, i.e., the speed divided by the number of
  iterations and the prediction is the predicted normalized speed multiplied by
  the number of iterations. Must be one of the following values:
  - `best_fit.linear`: fits the samples to t = mn+b where t is the predicted
    time, m is a variable, n is the number of iterations, and b is also a
    variable. This fit does not merely work on normalized speed.
  - `percentile`: see one_off_technique
  - `harmonic_mean`: see one_off_technique
  - `geometric_mean`: see one_off_technique
  - `arithmetic_mean`: see one_off_technique""",
    )
    iterated_percentile: float = Field(description="see one-off percentile")
    created_at: float = Field(
        description="when the progress bar was created in seconds since the unix epoch"
    )


ERROR_404_TYPE = Literal["not_found"]
"""the error type for a 404 response"""

ERROR_409_TYPE = Literal["step_name_already_exists"]
"""the error type for a 409 response"""


@router.post(
    "/",
    status_code=200,
    response_model=CreateProgressBarStepRequest,
    responses={
        "409": {
            "description": "conflict- a step already exists in this progress bar with this name",
            "model": StandardErrorResponse[ERROR_409_TYPE],
        },
        "404": {
            "description": "the progress bar step with that name does not exist",
            "model": StandardErrorResponse[ERROR_404_TYPE],
        },
        **STANDARD_ERRORS_BY_CODE,
    },
)
async def create_progress_bar_step(
    args: CreateProgressBarStepRequest,
    pbar_name: str,
    step_name: str,
    authorization: Optional[str] = Header(None),
):
    """creates a new step for a progress bar

    This accepts cognito or user token authentication. You can read more about the
    forms of authentication at [/rest_auth.html](/rest_auth.html)"""
    async with Itgs() as itgs:
        auth_result = await auth_any(itgs, authorization)
        if not auth_result.success:
            return auth_result.error_response
        if step_name == "default":
            return JSONResponse(
                content=StandardErrorResponse[ERROR_409_TYPE](
                    type="step_name_already_exists",
                    message="there is already a step in this progress bar with that name",
                ).dict(),
                status_code=409,
            )
        now = time.time()
        step_uid = "ep_pbs_" + secrets.token_urlsafe(8)
        conn = await itgs.conn()
        cursor = conn.cursor("strong")
        response = await cursor.executemany3(
            (
                (
                    """
                    WITH progress_bar_max_steps AS (
                        SELECT
                            progress_bars.id AS progress_bar_id,
                            MAX(progress_bar_steps.position) AS max_position
                        FROM progress_bars
                        JOIN progress_bar_steps ON progress_bar_steps.progress_bar_id = progress_bars.id
                        GROUP BY progress_bars.id
                    )
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
                        ?, ?,
                        progress_bar_max_steps.max_position + 1,
                        ?, ?, ?, ?, ?, ?
                    FROM progress_bars
                    JOIN progress_bar_max_steps ON progress_bar_max_steps.progress_bar_id = progress_bars.id
                    WHERE
                        EXISTS (
                            SELECT 1 FROM users
                            WHERE users.id = progress_bars.user_id
                              AND users.sub = ?
                        )
                        AND NOT EXISTS (
                            SELECT 1 FROM progress_bar_steps
                            WHERE
                              progress_bar_steps.progress_bar_id = progress_bars.id
                              AND progress_bar_steps.name = ?
                        )
                        AND progress_bars.name = ?
                    """,
                    (
                        step_uid,
                        step_name,
                        int(args.iterated),
                        args.one_off_technique,
                        args.one_off_percentile,
                        args.iterated_technique,
                        args.iterated_percentile,
                        now,
                        auth_result.result.sub,
                        step_name,
                        pbar_name,
                    ),
                ),
                (
                    """
                    UPDATE progress_bars
                    SET version = version + 1
                    WHERE
                        EXISTS (
                            SELECT 1 FROM progress_bar_steps
                            WHERE progress_bars.id = progress_bar_steps.progress_bar_id
                              AND progress_bar_steps.uid = ?
                        )
                    """,
                    (step_uid,),
                ),
                (
                    """
                    DELETE FROM progress_bar_traces
                    WHERE
                        EXISTS (
                            SELECT 1 FROM progress_bar_steps
                            WHERE progress_bar_traces.progress_bar_id = progress_bar_steps.progress_bar_id
                              AND progress_bar_steps.uid = ?
                        )
                    """,
                    (step_uid,),
                ),
            )
        )
        if (
            response.items[0].rows_affected is not None
            and response.items[0].rows_affected > 0
        ):
            pos_response = await cursor.execute(
                """
                SELECT position
                FROM progress_bar_steps
                WHERE uid = ?""",
                (step_uid,),
            )
            if not pos_response.results:
                return Response(status_code=503, headers={"retry-after": "1"})
            return JSONResponse(
                content=CreateProgressBarStepResponse(
                    uid=step_uid,
                    name=step_name,
                    position=pos_response.results[0][0],
                    iterated=args.iterated,
                    one_off_technique=args.one_off_technique,
                    one_off_percentile=args.one_off_percentile,
                    iterated_technique=args.iterated_technique,
                    iterated_percentile=args.iterated_percentile,
                    created_at=now,
                ).dict(),
                status_code=201,
            )
        response = await cursor.execute(
            """
            SELECT 1 FROM progress_bars
            WHERE
                EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = progress_bars.user_id
                        AND users.sub = ?
                )
            """,
            (auth_result.result.sub,),
        )
        if response.results:
            return JSONResponse(
                content=StandardErrorResponse[ERROR_409_TYPE](
                    type="step_name_already_exists",
                    message="there is already a step in this progress bar with that name",
                ).dict(),
                status_code=409,
            )
        return JSONResponse(
            content=StandardErrorResponse[ERROR_404_TYPE](
                type="not_found", message="there is no progress bar with that name"
            ).dict(),
            status_code=404,
        )
