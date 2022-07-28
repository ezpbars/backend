from fastapi import FastAPI
from fastapi.responses import JSONResponse
from itgs import Itgs

app = FastAPI(
    title="ezpbars",
    description="easy progress bars",
    version="1.0.0+alpha",
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
        if res.results[0] != (2,):
            return JSONResponse(
                content={"message": f"invalid row: {repr(res.results[0])}"},
                status_code=503,
            )
        return JSONResponse(
            content={"message": "rqlite cluster responding normally"}, status_code=200
        )
