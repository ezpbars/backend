from typing import Literal, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse, Response
from auth import auth_any
from itgs import Itgs

from models import STANDARD_ERRORS_BY_CODE, StandardErrorResponse

router = APIRouter()

ERROR_404_TYPE = Literal["pbar_not_found", "step_not_found"]
"""the error type for a 404 response"""

ERROR_409_TYPE = Literal["cannot_edit_default_step"]
"""the error type for a 409 response"""


class UpdateProgressBarStepRequest(BaseModel):
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
    one_off_percentile: int = Field(
        75,
        description="""required for non-iterated steps using the
  percentile technique. the percent of samples which should complete faster than
  the predicted amount of time. for example, `25` means a quarter of samples
  complete before the progress bar reaches the end. Typically, a high value,
  such as 90, is chosen, since it's better to surprise the user with a faster
  result, than to annoy them with a slower result.""",
        le=100,
        ge=0,
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
    iterated_percentile: int = Field(
        75, description="see one-off percentile", le=100, ge=0
    )


class UpdateProgressBarStepResponse(BaseModel):
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
    one_off_percentile: int = Field(
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
    iterated_percentile: int = Field(description="see one-off percentile")


@router.put(
    "/",
    response_model=UpdateProgressBarStepResponse,
    status_code=200,
    responses={
        "409": {
            "description": "conflict- you cannot edit the default step",
            "model": StandardErrorResponse[ERROR_409_TYPE],
        },
        "404": {
            "description": "progress bar or step with that name does not exist",
            "model": StandardErrorResponse[ERROR_404_TYPE],
        },
        **STANDARD_ERRORS_BY_CODE,
    },
)
async def update_progress_bar_step(
    args: UpdateProgressBarStepRequest,
    pbar_name: str,
    step_name: str,
    authorizaiton: Optional[str] = Header(None),
):
    """updates the progress bar step with the given name which belongs to the
    corresponsing progress bar. Only works if the progress bar belongs to you,
    and you cannot edit the default step

    This accepts cognito or user token authentication. You can read more about
    the forms of authentication at [/rest_auth.html](/rest_auth.html)"""
    async with Itgs() as itgs:
        auth_result = await auth_any(itgs, authorizaiton)
        if not auth_result.success:
            return auth_result.error_response
        if step_name == "default":
            return JSONResponse(
                content=StandardErrorResponse[ERROR_409_TYPE](
                    type="cannot_edit_default_step",
                    message="you may not edit the default step",
                )
            )
        conn = await itgs.conn()
        cursor = conn.cursor("none")
        response = await cursor.execute(
            """
            UPDATE progress_bar_steps
            SET
                one_off_technique = ?,
                one_off_percentile = ?,
                iterated_technique = ?,
                iterated_percentile = ?
            WHERE 
                progress_bar_steps.name = ?
                AND EXISTS (
                    SELECT 1 FROM progress_bars
                    WHERE progress_bars.name = ?
                      AND EXISTS (
                        SELECT 1 FROM users
                        WHERE users.id = progress_bars.user_id
                          AND users.sub = ?
                      )
                )
            """,
            (
                args.one_off_technique,
                args.one_off_percentile,
                args.iterated_technique,
                args.iterated_percentile,
                step_name,
                pbar_name,
                auth_result.result.sub,
            ),
        )
        if response.rows_affected is not None and response.rows_affected > 0:
            return JSONResponse(
                content=UpdateProgressBarStepResponse(
                    one_off_technique=args.one_off_technique,
                    one_off_percentile=args.one_off_percentile,
                    iterated_technique=args.iterated_technique,
                    iterated_percentile=args.iterated_percentile,
                ).dict(),
                status_code=200,
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
                content=StandardErrorResponse[ERROR_404_TYPE](
                    type="step_not_found",
                    message="there is no step with that name within this progress bar",
                ).dict(),
                status_code=404,
            )
        return JSONResponse(
            content=StandardErrorResponse[ERROR_404_TYPE](
                type="pbar_not_found",
                message="there is no progress bar with that name",
            ).dict(),
            status_code=404,
        )
