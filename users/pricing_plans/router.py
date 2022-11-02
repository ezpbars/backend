from fastapi import APIRouter
import users.pricing_plans.tiers.router


router = APIRouter()

router.include_router(users.pricing_plans.tiers.router.router, prefix="/tiers")
