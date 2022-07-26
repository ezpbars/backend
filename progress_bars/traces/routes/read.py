from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from auth import auth_any
from itgs import Itgs
from models import STANDARD_ERRORS_BY_CODE
from resources.filter_item import FilterItem, FilterItemModel
from resources.filter_text_item import FilterTextItem, FilterTextItemModel
from resources.sort import cleanup_sort, get_next_page_sort, reverse_sort
from resources.filter import sort_criterion, flattened_filters
from resources.sort_item import SortItem, SortItemModel
from resources.standard_text_operator import StandardTextOperator
from pypika import Table, Query, Parameter
from pypika.queries import QueryBuilder
from pypika.terms import Term

router = APIRouter()


class ProgressBarTrace(BaseModel):
    user_sub: str = Field(
        description="the sub for the user the progress bar belongs to"
    )
    progress_bar_name: str = Field(
        description="the name of the progress bar to which this step belongs"
    )
    uid: str = Field(description="the primary stable identifier for this progress bar")
    created_at: float = Field(
        description="when the progress bar trace was created in seconds since the unix epoch"
    )


PROGRESS_BAR_TRACE_SORT_OPTIONS = [
    SortItem[Literal["uid"], str],
    SortItem[Literal["progress_bar_name"], str],
    SortItem[Literal["created_at"], float],
]
ProgressBarTraceSortOption = Union[
    SortItemModel[Literal["uid"], str],
    SortItemModel[Literal["progress_bar_name"], str],
    SortItemModel[Literal["created_at"], float],
]


class ProgressBarTraceFilter(BaseModel):
    user_sub: Optional[FilterTextItemModel] = Field(
        None,
        description="the subject of the user the progress bar belongs to",
    )
    progress_bar_name: Optional[FilterTextItemModel] = Field(
        None, description="the name of the progress bar the step belongs to"
    )
    created_at: Optional[FilterItemModel[float]] = Field(
        None, description="when the trace was created"
    )


class ReadProgressBarTraceRequest(BaseModel):
    filters: Optional[ProgressBarTraceFilter] = Field(
        default_factory=ProgressBarTraceFilter, description="the filters to apply"
    )
    sort: Optional[List[ProgressBarTraceSortOption]] = Field(
        None, description="the order to sort by"
    )
    limit: int = Field(100, description="the maximum number of results", ge=1, le=100)


class ReadProgressBarTraceResponse(BaseModel):
    items: List[ProgressBarTrace] = Field(
        description="the items matching the results in the given sort"
    )
    next_page_sort: Optional[List[ProgressBarTraceSortOption]] = Field(
        description="if there is a next page of results, the sort to use to get the page"
    )


@router.post(
    "/search",
    response_model=ReadProgressBarTraceResponse,
    responses=STANDARD_ERRORS_BY_CODE,
)
async def read_progress_bar_trace(
    args: ReadProgressBarTraceRequest, authorization: Optional[str] = Header(None)
):
    """lists out the traces for a users progress bars; the user_sub filter will be forced to match
    the authorized user

    This accepts cognito or user token authentication. You can read more about the
    forms of authentication at [/rest_auth.html](/rest_auth.html)"""
    sort = [srt.to_result() for srt in (args.sort or [])]
    sort = cleanup_sort(PROGRESS_BAR_TRACE_SORT_OPTIONS, sort, ["uid"])
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
        items = await raw_read_progress_bar_trace(
            itgs, filters_to_apply, sort, args.limit + 1
        )
        next_page_sort: Optional[List[SortItem]] = None
        last_item: Optional[Dict[str, Any]] = None
        if len(items) > args.limit:
            items = items[: args.limit]
            last_item = item_pseudocolumns(items[-1])
        first_item: Optional[Dict[str, Any]] = None
        if items and any(s.after is not None for s in sort):
            rev_sort = reverse_sort(sort, "make_exclusive")
            rev_items = await raw_read_progress_bar_trace(
                itgs, filters_to_apply, rev_sort, 1
            )
            if rev_items:
                first_item = item_pseudocolumns(items[0])

        if first_item is not None or last_item is not None:
            next_page_sort = get_next_page_sort(first_item, last_item, sort)

        return JSONResponse(
            content=ReadProgressBarTraceResponse(
                items=items,
                next_page_sort=[s.to_model() for s in next_page_sort]
                if next_page_sort is not None
                else None,
            ).dict()
        )


async def raw_read_progress_bar_trace(
    itgs: Itgs,
    filters_to_apply: List[Tuple[str, Union[FilterItem, FilterTextItem]]],
    sort: List[SortItem],
    limit: int,
):
    """performs exactly the specified sort without pagination logic"""
    progress_bars = Table("progress_bars")
    progress_bar_traces = Table("progress_bar_traces")
    users = Table("users")

    query: QueryBuilder = (
        Query.from_(progress_bar_traces)
        .select(
            users.sub,
            progress_bars.name,
            progress_bar_traces.uid,
            progress_bar_traces.created_at,
        )
        .join(progress_bars)
        .on(progress_bars.id == progress_bar_traces.progress_bar_id)
        .join(users)
        .on(users.id == progress_bars.user_id)
    )
    qargs = []

    def pseudocolumn(key: str) -> Term:
        if key == "user_sub":
            return users.sub
        elif key == "progress_bar_name":
            return progress_bars.name
        elif key in ("uid", "created_at"):
            return progress_bar_traces.field(key)
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
    items: List[ProgressBarTrace] = []
    for row in response.results or []:
        items.append(
            ProgressBarTrace(
                user_sub=row[0], progress_bar_name=row[1], uid=row[2], created_at=row[3]
            )
        )
    return items


def item_pseudocolumns(item: ProgressBarTrace) -> dict:
    """returns the dictified item such that the keys in the return dict match
    the keys of the sort options"""
    return item.dict()
