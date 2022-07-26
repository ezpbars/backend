from fastapi import APIRouter
import users.tokens.router
import users.routes.create
import users.pricing_plans.router

router = APIRouter()
router.include_router(users.tokens.router.router, prefix="/tokens")
router.include_router(users.pricing_plans.router.router, prefix="/pricing_plans")
router.include_router(users.routes.create.router)
