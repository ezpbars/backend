from typing import Literal, Optional
from fastapi import APIRouter, Header
from fastapi.responses import Response, JSONResponse
from auth import auth_any
from itgs import Itgs
from models import STANDARD_ERRORS_BY_CODE, StandardErrorResponse

router = APIRouter()

ERROR_404_TYPE = Literal["pbar_not_found", "step_not_found"]
"""the error type for a 404 response"""

ERROR_409_TYPE = Literal["cannot_delete_default_step"]
"""the error type for a 409 response"""


@router.delete(
    "/",
    status_code=204,
    responses={
        "404": {
            "description": "not found - there is no progress bar step with that name",
            "model": StandardErrorResponse[ERROR_404_TYPE],
        },
        "409": {
            "description": "you may not delete the default step",
            "model": StandardErrorResponse[ERROR_409_TYPE],
        },
        **STANDARD_ERRORS_BY_CODE,
    },
)
async def delete_progress_bar_step(
    pbar_name: str, step_name: str, authorization: Optional[str] = Header(None)
):
    """deletes the progress bar step with the corresponding name within the
    progress bar specified, only works if the progress bar is owned by you, and
    will not delete the default step

    This accepts cognito or user token authentication. You can read more about the
    forms of authentication at [/rest_auth.html](/rest_auth.html)"""
    async with Itgs() as itgs:
        auth_result = await auth_any(itgs, authorization)
        if not auth_result.success:
            return auth_result.error_response
        if step_name == "default":
            return JSONResponse(
                content=StandardErrorResponse[ERROR_409_TYPE](
                    type="cannot_delete_default_step",
                    message="you may not delete the default step of a progress bar",
                ).dict(),
                status_code=409,
            )
        conn = await itgs.conn()
        cursor = conn.cursor("strong")
        response = await cursor.execute(
            """
            SELECT
                progress_bars.uid,
                progress_bars.version,
                progress_bar_steps.uid,
                progress_bar_steps.position
            FROM progress_bars
            LEFT OUTER JOIN progress_bar_steps ON progress_bars.id = progress_bar_steps.progress_bar_id
            WHERE
                progress_bars.name = ?
                AND progress_bar_steps.name = ?
                AND EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = progress_bars.user_id
                      AND users.sub = ?
                )
            """,
            (pbar_name, step_name, auth_result.result.sub),
        )
        if not response.results:
            return JSONResponse(
                content=StandardErrorResponse[ERROR_404_TYPE](
                    type="pbar_not_found",
                    message="there is no progress bar with that name",
                ).dict(),
                status_code=404,
            )
        (pbar_uid, pbar_version, step_uid, step_position) = response.results[0]
        if step_uid is None:
            return JSONResponse(
                content=StandardErrorResponse[ERROR_404_TYPE](
                    type="step_not_found", message="there is no step with that name"
                ).dict(),
                status_code=404,
            )
        response = await cursor.executemany3(
            (
                (
                    """
                    DELETE FROM progress_bar_steps
                    WHERE
                        progress_bar_steps.uid = ?
                        AND EXISTS (
                            SELECT 1 FROM progress_bars
                            WHERE progress_bars.uid = ?
                              AND progress_bars.version = ?
                        )
                    """,
                    (
                        step_uid,
                        pbar_uid,
                        pbar_version,
                    ),
                ),
                (
                    """
                    UPDATE progress_bar_steps
                    SET position = progress_bar_steps.position - 1
                    WHERE
                        progress_bar_steps.position > ?
                        AND EXISTS (
                            SELECT 1 FROM progress_bars
                            WHERE progress_bars.uid = ?
                              AND progress_bars.version = ?
                              AND progress_bars.id = progress_bar_steps.progress_bar_id
                        )
                    """,
                    (
                        step_position,
                        pbar_uid,
                        pbar_version,
                    ),
                ),
                (
                    """
                    DELETE FROM progress_bar_traces
                    WHERE
                        EXISTS (
                            SELECT 1 FROM progress_bars
                            WHERE progress_bars.id = progress_bar_traces.progress_bar_id
                              AND progress_bars.version = ?
                        )""",
                    (pbar_version,),
                ),
                (
                    """
                    UPDATE progress_bars
                    SET version = progress_bars.version + 1
                    WHERE
                        progress_bars.uid = ?
                        AND progress_bars.version = ?
                    """,
                    (
                        pbar_uid,
                        pbar_version,
                    ),
                ),
            )
        )
        if (
            response.items[0].rows_affected is None
            or response.items[0].rows_affected == 0
        ):
            return Response(status_code=503, headers={"retry-after": "1"})
        return Response(status_code=204)
