from fastapi import FastAPI
from fastapi.responses import JSONResponse
from itgs import Itgs
import secrets
import updater
import multiprocessing
import continuous_deployment.router

multiprocessing.Process(target=updater.listen_forever_sync, daemon=True).start()
app = FastAPI(
    title="ezpbars",
    description="easy progress bars",
    version="1.0.0+alpha",
    openapi_url="/api/1/openapi.json",
    docs_url="/api/1/docs",
)

app.include_router(
    continuous_deployment.router.router, prefix="/api/1/continuous_deployment"
)


@app.get("/")
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
