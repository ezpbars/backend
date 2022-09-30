from fastapi import APIRouter
import progress_bars.traces.routes.create
import progress_bars.traces.routes.read
import progress_bars.traces.routes.delete
import progress_bars.traces.steps.router

router = APIRouter()

router.include_router(progress_bars.traces.routes.create.router)
router.include_router(progress_bars.traces.routes.read.router)
router.include_router(progress_bars.traces.routes.delete.router)
router.include_router(progress_bars.traces.steps.router.router, prefix="/steps")
