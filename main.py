import os
import jwt
import time
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from starlette.middleware.cors import CORSMiddleware
from error_middleware import handle_request_error
from itgs import Itgs
import secrets
import updater
import migrations.main
import multiprocessing
import continuous_deployment.router
import users.router
import user_usages.router
import progress_bars.router
import examples.router

multiprocessing.Process(target=updater.listen_forever_sync, daemon=True).start()
multiprocessing.Process(target=migrations.main.main_sync, daemon=True).start()
app = FastAPI(
    title="ezpbars",
    description="easy progress bars",
    version="1.0.0+alpha",
    openapi_url="/api/1/openapi.json",
    docs_url="/api/1/docs",
    exception_handlers={Exception: handle_request_error},
)

if os.environ.get("ENVIRONMENT") == "dev":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:8888"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "HEAD", "PUT", "DELETE"],
        allow_headers=["Authorization"],
    )
app.include_router(
    continuous_deployment.router.router,
    prefix="/api/1/continuous_deployment",
    tags=["continuous_deployment"],
)
app.include_router(users.router.router, prefix="/api/1/users", tags=["users"])
app.include_router(
    user_usages.router.router, prefix="/api/1/user_usages", tags=["user_usages"]
)
app.include_router(
    progress_bars.router.router, prefix="/api/1/progress_bars", tags=["progress_bars"]
)
app.include_router(examples.router.router, prefix="/api/1/examples", tags=["examples"])
app.router.redirect_slashes = False


@app.get("/api/1")
def root():
    return {"message": "Hello World"}


@app.get("/api/1/test/rqdb")
async def test_rqdb():
    """Checks if the rqlite cluster is responding normally (2xx response)"""
    async with Itgs() as itgs:
        conn = await itgs.conn()
        res = await conn.cursor("none").execute("SELECT 2")
        if res.rowcount != 1:
            return JSONResponse(
                content={"message": f"invalid rowcount: {res.rowcount}"},
                status_code=503,
            )
        if res.results[0] != [2]:
            return JSONResponse(
                content={"message": f"invalid row: {repr(res.results[0])}"},
                status_code=503,
            )
        return JSONResponse(
            content={"message": "rqlite cluster responding normally"}, status_code=200
        )


@app.get("/api/1/test/redis")
async def test_redis():
    """Checks if the redis cluster is responding normally (2xx response)"""
    async with Itgs() as itgs:
        redis = await itgs.redis()

        test_key = "__test" + secrets.token_urlsafe(8)
        test_val = secrets.token_urlsafe(8)
        if not await redis.set(test_key, test_val):
            return JSONResponse(
                content={
                    "message": f"failed to set {test_key=} to {test_val=} (non-OK)"
                },
                status_code=503,
            )
        val: bytes = await redis.get(test_key)
        val = val.decode("utf-8")
        if val != test_val:
            return JSONResponse(
                content={
                    "message": f"expected {test_key=} to have {test_val=} but got {val=}"
                },
                status_code=503,
            )
        if not await redis.delete(test_key):
            return JSONResponse(
                content={"message": f"failed to delete {test_key=} (non-OK)"},
                status_code=503,
            )
        return JSONResponse(content={"message": "redis cluster responding normally"})


@app.get("/api/1/test/division")
async def test_division(dividend: int, divisor: int):
    """returns dividend/divisor - but gives an internal server error
    if divisor = 0; useful for testing error reporting
    """
    return JSONResponse(content={"quotient": dividend / divisor}, status_code=200)


@app.post("/api/1/test/dev_login")
async def dev_login(sub: str):
    """returns an id token under the id key for the given subject; only works in
    development mode"""
    if os.environ.get("ENVIRONMENT") != "dev":
        return Response(status_code=403)
    now = time.time()
    encoded_jwt = jwt.encode(
        {
            "sub": sub,
            "iss": os.environ["EXPECTED_ISSUER"],
            "exp": now + 3600,
            "aud": os.environ["AUTH_CLIENT_ID"],
            "token_use": "id",
        },
        os.environ["DEV_SECRET_KEY"],
        algorithm="HS256",
    )
    return JSONResponse(content={"id": encoded_jwt}, status_code=200)
