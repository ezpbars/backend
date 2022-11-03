from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from fastapi import APIRouter, Header
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
from pypika.terms import Term
from fastapi.responses import JSONResponse

router = APIRouter()


class UserUsage(BaseModel):
    user_sub: str = Field(description="The user's sub")
    uid: str = Field(description="the stable identifier for the usage record")
    hosted_invoice_url: Optional[str] = Field(
        description="The url for the hosted invoice page, for more information see https://stripe.com/docs/invoicing/hosted-invoice-page"
    )
    period_started_at: float = Field(
        description="The start of the billing period for this usage record, in seconds since the Unix epoch."
    )
    period_ended_at: float = Field(
        description="The end of the billing period for this usage record, in seconds since the Unix epoch."
    )
    traces: int = Field(
        description="The number of traces used during this billing period."
    )
    cost: Optional[float] = Field(
        description="How much the user was charged for this billing period."
    )


USER_USAGE_SORT_OPTIONS = [
    SortItem[Literal["period_started_at"], float],
    SortItem[Literal["uid"], str],
    SortItem[Literal["traces"], int],
    SortItem[Literal["cost"], float],
]
"""The sort options for the user usages."""
UserUsageSortOption = Union[
    SortItemModel[Literal["period_started_at"], float],
    SortItemModel[Literal["uid"], str],
    SortItemModel[Literal["traces"], int],
    SortItemModel[Literal["cost"], float],
]


class UserUsageFilter(BaseModel):
    user_sub: Optional[FilterTextItemModel] = Field(
        None,
        description="The user's sub",
    )
    period_started_at: Optional[FilterTextItemModel] = Field(
        None,
        description="The start of the billing period for this usage record, in seconds since the Unix epoch.",
    )


class ReadUserUsageRequest(BaseModel):
    filters: Optional[UserUsageFilter] = Field(
        default_factory=UserUsageFilter, description="The filters to apply."
    )
    sort: Optional[List[UserUsageSortOption]] = Field(
        description="the order to sort by"
    )
    limit: int = Field(
        100, description="The maximum number of results to return.", ge=1, le=100
    )


class ReadUserUsageResponse(BaseModel):
    items: List[UserUsage] = Field(
        description="the items matching the results in the given sort"
    )
    next_page_sort: Optional[List[UserUsageSortOption]] = Field(
        description="if there is a next page of results, the sort to use to get the next page"
    )


@router.post(
    "/search", response_model=ReadUserUsageResponse, responses=STANDARD_ERRORS_BY_CODE
)
async def read_user_usage(
    args: ReadUserUsageRequest, authorization: Optional[str] = Header(None)
):
    """Lists out the usage records; the user_sub filter will be forced to match
    the authorized user

    This accepts cognito or user token authentication. You can read more about the
    forms of authentication at [/rest_auth.html](/rest_auth.html)
    """
    sort = [srt.to_result() for srt in (args.sort or [])]
    sort = cleanup_sort(USER_USAGE_SORT_OPTIONS, sort, ["uid"])
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
        items = await raw_read_user_usages(itgs, filters_to_apply, sort, args.limit + 1)
        next_page_sort: Optional[List[SortItem]] = None
        last_item: Optional[Dict[str, Any]] = None
        if len(items) > args.limit:
            items = items[: args.limit]
            last_item = item_pseudocolumns(items[-1])
        first_item: Optional[Dict[str, Any]] = None
        if items and any(s.after is not None for s in sort):
            rev_sort = reverse_sort(sort, "make_exclusive")
            rev_items = await raw_read_user_usages(itgs, filters_to_apply, rev_sort, 1)
            if rev_items:
                first_item = item_pseudocolumns(items[0])

        if first_item is not None or last_item is not None:
            next_page_sort = get_next_page_sort(first_item, last_item, sort)

        return JSONResponse(
            content=ReadUserUsageResponse(
                items=items,
                next_page_sort=[s.to_model() for s in next_page_sort]
                if next_page_sort is not None
                else None,
            ).dict()
        )


async def raw_read_user_usages(
    itgs: Itgs,
    filters_to_apply: List[Tuple[str, Union[FilterItem, FilterTextItem]]],
    sort: List[SortItem],
    limit: int,
):
    """performs exactly the specified sort without pagination logic"""
    user_usages = Table("user_usages")
    stripe_invoices = Table("stripe_invoices")
    users = Table("users")

    query: QueryBuilder = (
        Query.from_(user_usages)
        .select(
            users.sub,
            user_usages.uid,
            stripe_invoices.hosted_invoice_url,
            user_usages.period_started_at,
            user_usages.period_ended_at,
            user_usages.traces,
            stripe_invoices.total,
        )
        .join(users)
        .on(users.id == user_usages.user_id)
        .left_join(stripe_invoices)
        .on(stripe_invoices.id == user_usages.stripe_invoice_id)
    )
    qargs = []

    def pseudocolumn(key: str) -> Term:
        if key == "user_sub":
            return users.sub
        elif key in ("period_started_at", "period_ended_at", "traces", "uid"):
            return user_usages.field(key)
        elif key in ("cost", "hosted_invoice_url"):
            return stripe_invoices.field(key)
        raise ValueError(f"unknown key: {key}")

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
    items: List[UserUsage] = []
    for row in response.results or []:
        items.append(
            UserUsage(
                user_sub=row[0],
                uid=row[1],
                hosted_invoice_url=row[2],
                period_started_at=row[3],
                period_ended_at=row[4],
                traces=row[5],
                cost=row[6],
            )
        )
    return items


def item_pseudocolumns(item: UserUsage) -> dict:
    """returns the dictified item such that the keys in the return dict match
    the keys of the sort options"""
    return item.dict()
