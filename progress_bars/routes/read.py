from pypika import Table, Query, Parameter
from pypika.queries import QueryBuilder
from pypika.terms import Term
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from auth import auth_any
from models import STANDARD_ERRORS_BY_CODE
from progress_bars.steps.routes.read import ProgressBarStep
from resources.filter import sort_criterion, flattened_filters
from resources.filter_item import FilterItem
from resources.sort import cleanup_sort, get_next_page_sort, reverse_sort
from resources.sort_item import SortItem, SortItemModel
from resources.filter_text_item import FilterTextItem, FilterTextItemModel
from itgs import Itgs
from resources.standard_text_operator import StandardTextOperator


class ProgressBar(BaseModel):
    user_sub: str = Field(
        description="the sub for the user the progress bar belongs to"
    )
    uid: str = Field(description="the primary stable identifyer for this progress bar")
    name: str = Field(
        description="the human-readable name for identifying this progress bar"
    )
    sampling_max_count: int = Field(
        description="the maximum number of samples to retain for prediction for this progress bar",
    )
    sampling_max_age_seconds: int = Field(
        description="the maximum age of samples to retain for prediction"
    )
    sampling_technique: str = Field(
        description="the technique to use when selecting samples to be used for prediction"
    )
    version: int = Field(
        description="the number of times the steps and traces had to be reset because we received a trace with different steps or it was updated via the api"
    )
    created_at: float = Field(
        description="when the progress bar was created in seconds since the unix epoch"
    )
    default_step_config: ProgressBarStep = Field(
        description="the default configuration used for steps"
    )


PROGRESS_BAR_SORT_OPTIONS = [
    SortItem[Literal["uid"], str],
    SortItem[Literal["name"], str],
    SortItem[Literal["created_at"], float],
    SortItem[Literal["sampling_max_count"], int],
]
"""the options for sorting the progress bars"""
ProgressBarSortOption = Union[
    SortItemModel[Literal["uid"], str],
    SortItemModel[Literal["name"], str],
    SortItemModel[Literal["created_at"], float],
    SortItemModel[Literal["sampling_max_count"], int],
]


class ProgressBarFilter(BaseModel):
    user_sub: Optional[FilterTextItemModel] = Field(
        None,
        description="the subject of the user the progress bar is for",
    )
    name: Optional[FilterTextItemModel] = Field(
        None, description="the name of the progress bar"
    )


class ReadProgressbarRequest(BaseModel):
    filters: Optional[ProgressBarFilter] = Field(
        default_factory=ProgressBarFilter, description="the filters to apply"
    )
    sort: Optional[List[ProgressBarSortOption]] = Field(
        None, description="the order to sort by"
    )
    limit: int = Field(
        100, description="the maximum number of results to return", ge=1, le=100
    )


class ReadProgressBarResponse(BaseModel):
    items: List[ProgressBar] = Field(
        description="the items matching the results in the given sort"
    )
    next_page_sort: Optional[List[ProgressBarSortOption]] = Field(
        description="if there is a next page of results, the sort to use to get the next page"
    )


router = APIRouter()


@router.post(
    "/search", response_model=ReadProgressBarResponse, responses=STANDARD_ERRORS_BY_CODE
)
async def read_progress_bars(
    args: ReadProgressbarRequest, authorization: Optional[str] = Header(None)
):
    """lists out the progress bars; the user_sub filter will be forced to match
    the authorized user

    This accepts cognito or user token authentication. You can read more about the
    forms of authentication at [/rest_auth.html](/rest_auth.html)
    """
    sort = [srt.to_result() for srt in (args.sort or [])]
    sort = cleanup_sort(PROGRESS_BAR_SORT_OPTIONS, sort, ["uid"])
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
        items = await raw_read_progress_bars(
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
            rev_items = await raw_read_progress_bars(
                itgs, filters_to_apply, rev_sort, 1
            )
            if rev_items:
                first_item = item_pseudocolumns(items[0])

        if first_item is not None or last_item is not None:
            next_page_sort = get_next_page_sort(first_item, last_item, sort)

        return JSONResponse(
            content=ReadProgressBarResponse(
                items=items,
                next_page_sort=[s.to_model() for s in next_page_sort]
                if next_page_sort is not None
                else None,
            ).dict()
        )


async def raw_read_progress_bars(
    itgs: Itgs,
    filters_to_apply: List[Tuple[str, Union[FilterItem, FilterTextItem]]],
    sort: List[SortItem],
    limit: int,
):
    """performs exactly the specified sort without pagination logic"""
    progress_bars = Table("progress_bars")
    users = Table("users")
    progress_bar_steps = Table("progress_bar_steps")

    query: QueryBuilder = (
        Query.from_(progress_bars)
        .select(
            users.sub,
            progress_bars.uid,
            progress_bars.name,
            progress_bars.sampling_max_count,
            progress_bars.sampling_max_age_seconds,
            progress_bars.sampling_technique,
            progress_bars.version,
            progress_bars.created_at,
            progress_bar_steps.uid,
            progress_bar_steps.iterated,
            progress_bar_steps.one_off_technique,
            progress_bar_steps.one_off_percentile,
            progress_bar_steps.iterated_technique,
            progress_bar_steps.iterated_percentile,
            progress_bar_steps.created_at,
        )
        .join(users)
        .on(users.id == progress_bars.user_id)
        .join(progress_bar_steps)
        .on(progress_bars.id == progress_bar_steps.progress_bar_id)
        .where(progress_bar_steps.name == Parameter("?"))
    )
    qargs = ["default"]

    def pseudocolumn(key: str) -> Term:
        if key == "user_sub":
            return users.sub
        elif key in ("uid", "name", "created_at", "sampling_max_count"):
            return progress_bars.field(key)
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
    items: List[ProgressBar] = []
    for row in response.results or []:
        items.append(
            ProgressBar(
                user_sub=row[0],
                uid=row[1],
                name=row[2],
                sampling_max_count=row[3],
                sampling_max_age_seconds=row[4],
                sampling_technique=row[5],
                version=row[6],
                created_at=row[7],
                default_step_config=ProgressBarStep(
                    uid=row[8],
                    name="default",
                    user_sub=row[0],
                    progress_bar_name=row[2],
                    position=0,
                    iterated=bool(row[9]),
                    one_off_technique=row[10],
                    one_off_percentile=row[11],
                    iterated_technique=row[12],
                    iterated_percentile=row[13],
                    created_at=row[14],
                ),
            )
        )
    return items


def item_pseudocolumns(item: ProgressBar) -> dict:
    """returns the dictified item such that the keys in the return dict match
    the keys of the sort options"""
    return item.dict()
