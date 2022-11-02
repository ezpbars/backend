from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from auth import auth_any
from itgs import Itgs
from models import STANDARD_ERRORS_BY_CODE
from resources.filter import flattened_filters, sort_criterion
from resources.filter_item import FilterItem
from resources.filter_text_item import FilterTextItem, FilterTextItemModel
from resources.sort import cleanup_sort, get_next_page_sort, reverse_sort
from resources.sort_item import SortItem, SortItemModel
from resources.standard_text_operator import StandardTextOperator
from pypika import Table, Query, Parameter
from pypika.queries import QueryBuilder
from pypika.terms import ExistsCriterion, Term


class UserPricingPlanTier(BaseModel):
    user_sub: str = Field(description="the sub of the user")
    uid: str = Field(description="the uid of the pricing plan tier")
    position: int = Field(description="the position of the tier in the pricing plan")
    units: Optional[int] = Field(description="the number of units the tier covers")
    unit_amount: int = Field(description="the amount of traces per unit")
    unit_price_cents: int = Field(
        description="the price of each unit for this tier in cents"
    )


USER_PRICING_PLAN_TIER_SORT_OPTIONS = [
    SortItem[Literal["uid"], str],
    SortItem[Literal["position"], int],
    SortItem[Literal["units"], int],
    SortItem[Literal["unit_price_cents"], int],
]
"""the options for sorting the user pricing plan tiers"""
UserPricingPlanTierSortOption = Union[
    SortItemModel[Literal["uid"], str],
    SortItemModel[Literal["position"], int],
    SortItemModel[Literal["units"], int],
    SortItemModel[Literal["unit_price_cents"], int],
]


class UserPricingPlanTierFilter(BaseModel):
    user_sub: Optional[FilterTextItemModel] = Field(
        None,
        description="the subject of the user the progress bar is for",
    )
    position: Optional[FilterTextItemModel] = Field(
        None,
        description="the position of the tier in the pricing plan",
    )


class ReadUserPricingPlanTiersRequest(BaseModel):
    filters: Optional[UserPricingPlanTierFilter] = Field(
        default_factory=UserPricingPlanTierFilter, description="the filters to apply"
    )
    sort: Optional[List[UserPricingPlanTierSortOption]] = Field(
        None, description="the order to sort by"
    )
    limit: int = Field(
        100, description="the maximum number of results to return", ge=1, le=100
    )


class ReadUserPricingPlanTiersResponse(BaseModel):
    items: List[UserPricingPlanTier] = Field(
        description="the user pricing plan tiers that match the request"
    )
    next_page_sort: Optional[List[UserPricingPlanTierSortOption]] = Field(
        description="the sort to use to get the next page of results, if there is one"
    )


router = APIRouter()


@router.post(
    "/search",
    response_model=ReadUserPricingPlanTiersResponse,
    responses=STANDARD_ERRORS_BY_CODE,
)
async def read_user_pricing_plan_tiers(
    args: ReadUserPricingPlanTiersRequest,
    authorization: Optional[str] = Header(None),
):
    """lists out the user pricing plan tiers; the user_sub filter will be forced to
    match the authorized user

    This accepts cognito or user token authentication. You can read more about the
    forms of authentication at [/rest_auth.html](/rest_auth.html)
    """
    sort = [srt.to_result() for srt in (args.sort or [])]
    sort = cleanup_sort(USER_PRICING_PLAN_TIER_SORT_OPTIONS, sort, ["uid"])
    async with Itgs() as itgs:
        auth_result = await auth_any(itgs, authorization)
        if not auth_result.success:
            return auth_result.error_response
        args.filters.user_sub = FilterTextItemModel(
            operator=StandardTextOperator.EQUAL_CASE_SENSITIVE,
            value=auth_result.result.sub,
        )
        filters_to_apply = flattened_filters(
            dict(
                (k, v.to_result())
                for k, v in args.filters.__dict__.items()
                if v is not None
            )
            if args.filters is not None
            else dict()
        )
        tiers = await raw_read_user_pricing_plan_tiers(
            itgs, filters_to_apply, sort, args.limit + 1
        )
        next_page_sort: Optional[List[SortItem]] = None
        last_item: Optional[Dict[str, Any]] = None
        if len(tiers) > args.limit:
            tiers = tiers[: args.limit]
            last_item = item_pseudocolumns(tiers[-1])
        first_item: Optional[Dict[str, Any]] = None
        if tiers and any(s.after is not None for s in sort):
            rev_sort = reverse_sort(sort, "make_exclusive")
            rev_tiers = await raw_read_user_pricing_plan_tiers(
                itgs, filters_to_apply, rev_sort, 1
            )
            if rev_tiers:
                first_item = item_pseudocolumns(tiers[0])

        if first_item is not None or last_item is not None:
            next_page_sort = get_next_page_sort(first_item, last_item, sort)

        return JSONResponse(
            content=ReadUserPricingPlanTiersResponse(
                items=tiers,
                next_page_sort=[s.to_model() for s in next_page_sort]
                if next_page_sort is not None
                else None,
            ).dict()
        )


async def raw_read_user_pricing_plan_tiers(
    itgs: Itgs,
    filters_to_apply: List[Tuple[str, Union[FilterItem, FilterTextItem]]],
    sort: List[SortItem],
    limit: int,
):
    """performs exactly the specified sort without pagination logic"""
    user_pricing_plans = Table("user_pricing_plans")
    pricing_plan_tiers = Table("pricing_plan_tiers")
    users = Table("users")
    pricing_plans = Table("pricing_plans")

    query: QueryBuilder = (
        Query.from_(users)
        .select(
            users.sub,
            pricing_plan_tiers.uid,
            pricing_plan_tiers.position,
            pricing_plan_tiers.units,
            pricing_plans.unit_amount,
            pricing_plan_tiers.unit_price_cents,
        )
        .join(user_pricing_plans)
        .on(users.id == user_pricing_plans.user_id)
        .join(pricing_plan_tiers)
        .on(user_pricing_plans.pricing_plan_id == pricing_plan_tiers.pricing_plan_id)
        .join(pricing_plans)
        .on(pricing_plan_tiers.pricing_plan_id == pricing_plans.id)
    )

    qargs = []

    def pseudocolumn(key: str) -> Term:
        if key == "user_sub":
            return users.sub
        elif key == "unit_amount":
            return pricing_plans.unit_amount
        elif key in ("uid", "position", "units", "unit_price_cents"):
            return pricing_plan_tiers.field(key)
        raise ValueError(f"unknown key {key}")

    for key, filter in filters_to_apply:
        query = query.where(filter.applied_to(pseudocolumn(key), qargs))

    query = query.where(sort_criterion(sort, pseudocolumn, qargs))

    for srt in sort:
        query = query.orderby(pseudocolumn(srt.key), order=srt.order)

    query = query.limit(Parameter("?"))
    qargs.append(limit)

    conn = await itgs.conn()
    cursor = conn.cursor("none")
    response = await cursor.execute(query.get_sql(), qargs)
    tiers: List[UserPricingPlanTier] = []
    for row in response.results or []:
        tiers.append(
            UserPricingPlanTier(
                user_sub=row[0],
                uid=row[1],
                position=row[2],
                units=row[3],
                unit_amount=row[4],
                unit_price_cents=row[5],
            )
        )
    return tiers


def item_pseudocolumns(tier: UserPricingPlanTier) -> dict:
    """returns the dictified item such that the keys in the return dict match
    the keys of the sort options"""
    return tier.dict()
