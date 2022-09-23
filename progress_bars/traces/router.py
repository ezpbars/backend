from fastapi import APIRouter
import progress_bars.traces.routes.delete
import progress_bars.traces.routes.read

router = APIRouter()

router.include_router(progress_bars.traces.routes.delete.router)
router.include_router(progress_bars.traces.routes.read.router)
