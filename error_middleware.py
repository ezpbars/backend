from fastapi import Request, Response
from fastapi.responses import PlainTextResponse
from itgs import Itgs
import traceback


async def handle_error(request: Request, exc: Exception) -> Response:
    message = "\n".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)[-5:]
    )
    message = f"```\n{message}\n```"
    async with Itgs() as itgs:
        slack = await itgs.slack()
        await slack.send_web_error_message(message, "an error occurred in backend")
    return PlainTextResponse(content="internal server error", status_code=500)
