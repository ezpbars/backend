from fastapi import APIRouter
import users.pricing_plans.tiers.routes.read

router = APIRouter()

router.include_router(users.pricing_plans.tiers.routes.read.router)
