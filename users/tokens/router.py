from fastapi import APIRouter
import users.tokens.routes.create

router = APIRouter()
router.include_router(users.tokens.routes.create.router)
