from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Header
from pydantic import BaseModel, Field
from auth import auth_any
from itgs import Itgs

router = APIRouter()


class CurrentUserUsageResponse(BaseModel):
    traces: int = Field(
        description="the number of traces the user has created during the current month so far"
    )
    period_start_at: float = Field(
        description="the beginning of the current month in seconds since the unix epoch"
    )


@router.get("/get_current", response_model=CurrentUserUsageResponse, status_code=200)
async def get_current_usage(
    authorization: Optional[str] = Header(None),
):
    """returns the current usage for this month for the user

    This accepts cognito or user token authentication. You can read more about the
    forms of authentication at [/rest_auth.html](/rest_auth.html)
    """
    async with Itgs() as itgs:
        auth_result = await auth_any(itgs, authorization)
        if not auth_result.success:
            return auth_result.error_response
        redis = await itgs.redis()
        now = datetime.now(timezone.utc)
        response = await redis.hget(
            f"tcount:{now.year}:{now.month}",
            auth_result.result.sub,
        )
        if response is None:
            return CurrentUserUsageResponse(
                traces=0,
                period_start_at=now.replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                ).timestamp(),
            )
        return CurrentUserUsageResponse(
            traces=int(response),
            period_start_at=now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            ).timestamp(),
        )
