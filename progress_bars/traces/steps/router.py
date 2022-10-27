from fastapi import APIRouter
import progress_bars.traces.steps.routes.create
import progress_bars.traces.steps.routes.read

router = APIRouter()

router.include_router(progress_bars.traces.steps.routes.create.router)
router.include_router(progress_bars.traces.steps.routes.read.router)
