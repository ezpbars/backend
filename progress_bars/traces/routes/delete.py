from typing import Literal, Optional
from fastapi import APIRouter, Header
from fastapi.responses import Response, JSONResponse
from auth import auth_any
from itgs import Itgs
from models import STANDARD_ERRORS_BY_CODE, StandardErrorResponse

router = APIRouter()

ERROR_404_TYPE = Literal["pbar_not_found", "trace_not_found"]
"""the error type for a 404 response"""


@router.delete(
    "/",
    status_code=204,
    responses={
        "404": {
            "description": "not found - there is no progress bar trace with that uid",
            "model": StandardErrorResponse[ERROR_404_TYPE],
        },
        **STANDARD_ERRORS_BY_CODE,
    },
)
async def delete_progress_bar_trace(
    pbar_name: str, trace_uid: str, authorization: Optional[str] = Header(None)
):
    """deletes the progress bar trace with the corresponding name within the
    progress bar specified, only works if the progress bar is owned by you

    This accepts cognito or user token authentication. You can read more about the
    forms of authentication at [/rest_auth.html](/rest_auth.html)"""
    async with Itgs() as itgs:
        auth_result = await auth_any(itgs, authorization)
        if not auth_result.success:
            return auth_result.error_response
        conn = await itgs.conn()
        cursor = conn.cursor("strong")
        response = await cursor.execute(
            """
            DELETE FROM progress_bar_traces
            WHERE
                progress_bar_traces.uid = ?
                AND EXISTS (
                    SELECT 1 FROM progress_bars
                    WHERE progress_bars.name = ?
                      AND progress_bars.id = progress_bar_traces.progress_bar_id
                      AND EXISTS (
                        SELECT 1 FROM users
                        WHERE users.id = progress_bars.user_id
                          AND users.sub = ?
                      )
                )
            """,
            (
                trace_uid,
                pbar_name,
                auth_result.result.sub,
            ),
        )
        if response.rows_affected is None or response.rows_affected == 0:
            response = await cursor.execute(
                """
                SELECT 1 FROM progress_bars
                WHERE progress_bars.name = ?
                  AND EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = progress_bars.user_id
                      AND users.sub = ?
                  )
                """,
                (
                    pbar_name,
                    auth_result.result.sub,
                ),
            )
            if not response.results:
                return JSONResponse(
                    content=StandardErrorResponse[ERROR_404_TYPE](
                        type="pbar_not_found",
                        message="there is no progress bar with that name",
                    ).dict(),
                    status_code=404,
                )
            return JSONResponse(
                content=StandardErrorResponse[ERROR_404_TYPE](
                    type="trace_not_found",
                    message="there is no progress bar trace with that uid",
                ).dict(),
                status_code=404,
            )
        return Response(status_code=204)
