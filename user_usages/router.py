from fastapi import APIRouter
import user_usages.routes.read_current
import user_usages.routes.read

router = APIRouter()

router.include_router(user_usages.routes.read_current.router)
router.include_router(user_usages.routes.read.router)
