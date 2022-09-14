from fastapi import APIRouter
import progress_bars.routes.create
import progress_bars.routes.read
import progress_bars.routes.update
import progress_bars.routes.delete

router = APIRouter()

router.include_router(progress_bars.routes.create.router)
router.include_router(progress_bars.routes.read.router)
router.include_router(progress_bars.routes.update.router)
router.include_router(progress_bars.routes.delete.router)
