from fastapi import APIRouter
import examples.routes.job
import examples.routes.get

router = APIRouter()

router.include_router(examples.routes.job.router)
router.include_router(examples.routes.get.router)
