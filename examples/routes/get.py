from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse

from itgs import Itgs
from models import StandardErrorResponse

router = APIRouter()


class ExampleJobResponse(BaseModel):
    number: int = Field(description="the random number between 1 and 10000")


ERROR_404_TYPE = Literal["not_found"]
"""the type of error for a 404 response"""


@router.get(
    "/job",
    response_model=ExampleJobResponse,
    status_code=200,
    responses={
        "404": {
            "description": "there was no result found for that job, either the job has not completed or the result expired (typically after ten minutes)",
            "model": StandardErrorResponse[ERROR_404_TYPE],
        }
    },
)
async def get_example_result(uid: str):
    """returns the result of the [example job](#/examples/example_job_api_1_examples_job_post) from redis"""
    async with Itgs() as itgs:
        redis = await itgs.redis()
        response = await redis.get(f"example:{uid}")
        if response is None:
            return JSONResponse(
                content=StandardErrorResponse[ERROR_404_TYPE](
                    type="not_found",
                    message="there was no result found for that job, either the job has not completed or the result expired (typically after ten minutes)",
                ).dict(),
                status_code=404,
            )
        return JSONResponse(
            content=ExampleJobResponse(number=int(response)),
            status_code=200,
        )
