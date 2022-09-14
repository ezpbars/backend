from typing import Literal, Optional
from fastapi import APIRouter, Header
from fastapi.responses import Response, JSONResponse
from auth import auth_any
from itgs import Itgs
from models import STANDARD_ERRORS_BY_CODE, StandardErrorResponse

router = APIRouter()

ERROR_404_TYPE = Literal["not_found"]
"""the error type for a 404 response"""


@router.delete(
    "/",
    status_code=204,
    responses={
        "404": {
            "description": "not found - ther is no progress bar with that name",
            "model": StandardErrorResponse[ERROR_404_TYPE],
        },
        **STANDARD_ERRORS_BY_CODE,
    },
)
async def delete_progress_bar(name: str, authorization: Optional[str] = Header(None)):
    """deletes the progress bar with the corresponding name, only works if the
    progress bar is owned by you

    This accepts cognito or user token authentication. You can read more about the
    forms of authentication at [/rest_auth.html](/rest_auth.html)"""
    async with Itgs() as itgs:
        auth_result = await auth_any(itgs, authorization)
        if not auth_result.success:
            return auth_result.error_response
        conn = await itgs.conn()
        cursor = conn.cursor("none")
        response = await cursor.execute(
            """DELETE FROM progress_bars
            WHERE
                progress_bars.name = ?
                AND EXISTS (
                    SELECT 1 FROM users
                    WHERE users.id = progress_bars.user_id
                      AND users.sub = ?
                )
            """,
            (name, auth_result.result.sub),
        )
        if response.rows_affected is not None and response.rows_affected > 0:
            return Response(status_code=204)
        return JSONResponse(
            content=StandardErrorResponse[ERROR_404_TYPE](
                type="not_found", message="progress bar not found"
            ).dict(),
            status_code=404,
        )
