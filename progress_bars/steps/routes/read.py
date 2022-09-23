from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from auth import auth_any
from itgs import Itgs
from models import STANDARD_ERRORS_BY_CODE
from resources.filter_item import FilterItem
from resources.filter_text_item import FilterTextItem, FilterTextItemModel
from resources.sort import cleanup_sort, get_next_page_sort, reverse_sort
from resources.filter import sort_criterion, flattened_filters
from resources.sort_item import SortItem, SortItemModel
from resources.standard_text_operator import StandardTextOperator
from pypika import Table, Query, Parameter
from pypika.queries import QueryBuilder
from pypika.terms import Term

router = APIRouter()


class ProgressBarStep(BaseModel):
    user_sub: str = Field(
        description="the sub for the user the progress bar belongs to"
    )
    progress_bar_name: str = Field(
        description="the name of the progress bar to which this step belongs"
    )
    uid: str = Field(description="the primary stable identifyer for this progress bar")
    name: str = Field(
        description="the human-readable name for identifying this progress bar"
    )
    position: int = Field(
        description="when the step occurs within the overall task, i.e., 1 is the first step. The default step has a position of 0",
    )
    iterated: bool = Field(
        description="""True if the step is iterated, i.e., it consists of
  many, identical, smaller steps, False for a one-off step, i.e., a step which is
  not repeated. Ignored for the default step"""
    )
    one_off_technique: Literal[
        "percentile", "harmonic_mean", "geometric_mean", "arithmetic_mean"
    ] = Field(
        "percentile",
        description="""required for non-iterated i.e., one-off
steps. The technique to use to predict the time step will take. one of the
following values:
- `percentile`: the fastest amount of time slower than a fixed percentage of
  the samples, see also: one_off_percentile
- `harmonic_mean`: the harmonic mean of the samples, https://en.wikipedia.org/wiki/Harmonic_mean
- `geometric_mean`: the geometric mean of the samples, https://en.wikipedia.org/wiki/Geometric_mean
- `arithmetic_mean`: the arithmetic mean of the samples, https://en.wikipedia.org/wiki/Arithmetic_mean""",
    )
    one_off_percentile: int = Field(
        description="""required for non-iterated steps using the
  percentile technique. the percent of samples which should complete faster than
  the predicted amount of time. for example, `25` means a quarter of samples
  complete before the progress bar reaches the end. Typically, a high value,
  such as 90, is chosen, since it's better to surprise the user with a faster
  result, than to annoy them with a slower result.""",
    )
    iterated_technique: Literal[
        "best_fit.linear",
        "percentile",
        "harmonic_mean",
        "geometric_mean",
        "arithmetic_mean",
    ] = Field(
        description="""required for iterated steps. The technique
  used to predict the time the step takes, unless otherwise noted, the technique
  is applied to the normalized speed, i.e., the speed divided by the number of
  iterations and the prediction is the predicted normalized speed multiplied by
  the number of iterations. Must be one of the following values:
  - `best_fit.linear`: fits the samples to t = mn+b where t is the predicted
    time, m is a variable, n is the number of iterations, and b is also a
    variable. This fit does not merely work on normalized speed.
  - `percentile`: see one_off_technique
  - `harmonic_mean`: see one_off_technique
  - `geometric_mean`: see one_off_technique
  - `arithmetic_mean`: see one_off_technique""",
    )
    iterated_percentile: int = Field(description="see one-off percentile")
    created_at: float = Field(
        description="when the progress bar was created in seconds since the unix epoch"
    )


PROGRESS_BAR_STEP_SORT_OPTIONS = [
    SortItem[Literal["uid"], str],
    SortItem[Literal["name"], str],
    SortItem[Literal["progress_bar_name"], str],
    SortItem[Literal["position"], int],
    SortItem[Literal["created_at"], float],
]
ProgressBarStepSortOption = Union[
    SortItemModel[Literal["uid"], str],
    SortItemModel[Literal["name"], str],
    SortItemModel[Literal["progress_bar_name"], str],
    SortItemModel[Literal["position"], int],
    SortItemModel[Literal["created_at"], float],
]


class ProgressBarStepFilter(BaseModel):
    user_sub: Optional[FilterTextItemModel] = Field(
        None,
        description="the subject of the user the progress bar is for",
    )
    name: Optional[FilterTextItemModel] = Field(
        None, description="the name of the step"
    )
    progress_bar_name: Optional[FilterTextItemModel] = Field(
        None, description="the name of the progress bar the step belongs to"
    )


class ReadProgressBarStepRequest(BaseModel):
    filters: Optional[ProgressBarStepFilter] = Field(
        None, description="the filters to apply"
    )
    sort: Optional[List[ProgressBarStepSortOption]] = Field(
        None, description="the order to sort by"
    )
    limit: int = Field(
        100, description="the maximum number of results to return", ge=1, le=100
    )


class ReadProgressBarStepResponse(BaseModel):
    items: List[ProgressBarStep] = Field(
        description="the items matching the results in the given sort"
    )
    next_page_sort: Optional[List[ProgressBarStepSortOption]] = Field(
        description="if there is a next page of results, the sort to use to get the next page"
    )


@router.post(
    "/search",
    response_model=ReadProgressBarStepResponse,
    responses=STANDARD_ERRORS_BY_CODE,
)
async def read_progress_bar_steps(
    args: ReadProgressBarStepRequest, authorization: Optional[str] = Header(None)
):
    """lists out the steps for a users progress bars; the user_sub filter will be forced to match
    the authorized user

    This accepts cognito or user token authentication. You can read more about the
    forms of authentication at [/rest_auth.html](/rest_auth.html)
    """
    sort = [srt.to_result() for srt in (args.sort or [])]
    sort = cleanup_sort(PROGRESS_BAR_STEP_SORT_OPTIONS, sort, ["uid"])
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
        items = await raw_read_progress_bar_steps(
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
            rev_items = await raw_read_progress_bar_steps(
                itgs, filters_to_apply, rev_sort, 1
            )
            if rev_items:
                first_item = item_pseudocolumns(items[0])

        if first_item is not None or last_item is not None:
            next_page_sort = get_next_page_sort(first_item, last_item, sort)

        return JSONResponse(
            content=ReadProgressBarStepResponse(
                items=items,
                next_page_sort=[s.to_model() for s in next_page_sort]
                if next_page_sort is not None
                else None,
            ).dict()
        )


async def raw_read_progress_bar_steps(
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
        Query.from_(progress_bar_steps)
        .select(
            users.sub,
            progress_bars.name,
            progress_bar_steps.uid,
            progress_bar_steps.name,
            progress_bar_steps.position,
            progress_bar_steps.iterated,
            progress_bar_steps.one_off_technique,
            progress_bar_steps.one_off_percentile,
            progress_bar_steps.iterated_technique,
            progress_bar_steps.iterated_percentile,
            progress_bar_steps.created_at,
        )
        .join(progress_bars)
        .on(progress_bars.id == progress_bar_steps.progress_bar_id)
        .join(users)
        .on(users.id == progress_bars.user_id)
    )
    qargs = []

    def pseudocolumn(key: str) -> Term:
        if key == "user_sub":
            return users.sub
        elif key == "progress_bar_name":
            return progress_bars.name
        elif key in ("uid", "name", "created_at", "position"):
            return progress_bar_steps.field(key)
        raise ValueError(f"unknown key:{key}")

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
    items: List[ProgressBarStep] = []
    for row in response.results or []:
        items.append(
            ProgressBarStep(
                user_sub=row[0],
                progress_bar_name=row[1],
                uid=row[2],
                name=row[3],
                position=row[4],
                iterated=bool(row[5]),
                one_off_technique=row[6],
                one_off_percentile=row[7],
                iterated_technique=row[8],
                iterated_percentile=row[9],
                created_at=row[10],
            )
        )
    return items


def item_pseudocolumns(item: ProgressBarStep) -> dict:
    """returns the dictified item such that the keys in the return dict match
    the keys of the sort options"""
    return item.dict()
