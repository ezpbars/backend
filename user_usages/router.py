from fastapi import APIRouter
import user_usages.routes.read_current

router = APIRouter()

router.include_router(user_usages.routes.read_current.router)
