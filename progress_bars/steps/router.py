from fastapi import APIRouter
import progress_bars.steps.routes.create
import progress_bars.steps.routes.read
import progress_bars.steps.routes.update
import progress_bars.steps.routes.delete

router = APIRouter()

router.include_router(progress_bars.steps.routes.create.router)
router.include_router(progress_bars.steps.routes.read.router)
router.include_router(progress_bars.steps.routes.update.router)
router.include_router(progress_bars.steps.routes.delete.router)
