from typing import Literal, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse

from itgs import Itgs

router = APIRouter()


class ExampleJobResponseData(BaseModel):
    number: int = Field(description="the random number between 1 and 10000")


class ExampleJobResponse(BaseModel):
    data: Optional[ExampleJobResponseData] = Field(description="the response data")
    status: Literal["complete", "incomplete"] = Field(
        description="the status of the example job"
    )


@router.get("/job", response_model=ExampleJobResponse, status_code=200)
async def get_example_result(uid: str):
    """returns the result of the [example job](#/examples/example_job_api_1_examples_job_post) from redis"""
    async with Itgs() as itgs:
        redis = await itgs.redis()
        response = await redis.get(f"example:{uid}")
        if response is None:
            return JSONResponse(
                content=ExampleJobResponse(data=None, status="incomplete").dict(),
                status_code=200,
            )
        return JSONResponse(
            content=ExampleJobResponse(
                data=ExampleJobResponseData(number=int(response)), status="complete"
            ).dict(),
            status_code=200,
        )
