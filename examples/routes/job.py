import os
import time
import aiohttp
from fastapi import APIRouter
from pydantic import BaseModel, Field
import secrets
from fastapi.responses import JSONResponse
from example_user import get_example_user_token
from itgs import Itgs

router = APIRouter()


class ExampleRequest(BaseModel):
    duration: int = Field(
        description="the duration of the example in seconds", ge=1, le=10
    )
    stdev: int = Field(
        description="the standard deviation of the example in seconds", ge=1, le=3
    )


class ExampleResponse(BaseModel):
    uid: str = Field(description="the primary stable identifier for this example")
    sub: str = Field(description="the sub for the example user")
    pbar_name: str = Field(
        description="the name of the progress bar created for the example user"
    )


@router.post(
    "/job",
    response_model=ExampleResponse,
    status_code=200,
)
async def example_job(args: ExampleRequest):
    """starts an example job, which computes a random number between 1 and
    10000 asynchronously.
    the result can be retrieved using the [get_example_result](#/examples/get_example_result_api_1_examples_job_get) endpoint
    """
    async with Itgs() as itgs:
        uid = "ep_t_" + secrets.token_urlsafe(16)
        sub = os.environ["EXAMPLE_USER_SUB"]
        pbar_name = f"example_{args.stdev}"
        jobs = await itgs.jobs()
        token = await get_example_user_token(itgs)

        async with aiohttp.ClientSession() as session:
            await session.post(
                url=f'{os.environ["ROOT_BACKEND_URL"]}/api/1/progress_bars/traces/',
                headers={"Authorization": f"bearer {token}"},
                json={
                    "pbar_name": pbar_name,
                    "uid": uid,
                    "step_name": "queuing",
                    "now": time.time(),
                },
            )
        await jobs.enqueue(
            "runners.handle_example_job",
            sub=sub,
            uid=uid,
            pbar_name=pbar_name,
            duration=args.duration,
            stdev=args.stdev,
        )
        return JSONResponse(
            content=ExampleResponse(uid=uid, sub=sub, pbar_name=pbar_name).dict(),
            status_code=200,
        )
