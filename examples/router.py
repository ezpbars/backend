from fastapi import APIRouter
import examples.routes.example_job
import examples.routes.example_get

router = APIRouter()

router.include_router(examples.routes.example_job.router)
router.include_router(examples.routes.example_get.router)
