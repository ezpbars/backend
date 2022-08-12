from fastapi import APIRouter
import users.tokens.router

router = APIRouter()
router.include_router(users.tokens.router.router, prefix="/tokens")
