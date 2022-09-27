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
from pypika.functions import Coalesce
from pypika.queries import QueryBuilder
from pypika.terms import Term


router = APIRouter()


class ProgressBarTraceStep(BaseModel):
    user_sub: str = Field(
        description="the sub for the user the progress bar belongs to"
    )
    progress_bar_name: str = Field(
        description="the name of the progress bar to which the step belongs"
    )
    progress_bar_step_name: str = Field(
        description="the name of the progress bar step to which the trace step belongs"
    )
    progress_bar_step_position: int = Field(
        description="the position of the progress bar step to which the trace step belongs"
    )
    progress_bar_trace_uid: str = Field(
        description="the uid of the progress bar trace to which the trace step belongs"
    )
    uid: str = Field(description="the primary stable external identifier")
    iterations: Optional[int] = Field(
        description="if the step is iterated, how many iterations were needed for this step in this trace"
    )
    started_at: float = Field(
        description="the time the step began for this trace in seconds since the unix epoch"
    )
    finished_at: float = Field(
        description="the time the step finished for this trace in seconds since the unix epoch"
    )


PROGRESS_BAR_TRACE_STEP_SORT_OPTIONS = [
    SortItem[Literal["uid"], str],
    SortItem[Literal["progress_bar_name"], str],
    SortItem[Literal["progress_bar_step_name"], str],
    SortItem[Literal["progress_bar_step_position"], int],
    SortItem[Literal["started_at"], float],
    SortItem[Literal["finished_at"], float],
    SortItem[Literal["duration"], float],
    SortItem[Literal["normalized_duration"], float],
]
ProgressBarTraceStepSortOption = Union[
    SortItemModel[Literal["uid"], str],
    SortItemModel[Literal["progress_bar_name"], str],
    SortItemModel[Literal["progress_bar_step_name"], str],
    SortItemModel[Literal["progress_bar_step_position"], int],
    SortItemModel[Literal["started_at"], float],
    SortItemModel[Literal["finished_at"], float],
    SortItemModel[Literal["duration"], float],
    SortItemModel[Literal["normalized_duration"], float],
]


class ProgressBarTraceStepFilter(BaseModel):
    user_sub: Optional[FilterTextItemModel] = Field(
        None,
        description="the sub for the user the progress bar belongs to",
    )
    progress_bar_name: Optional[FilterTextItemModel] = Field(
        None,
        description="the name of the progress bar to which the step belongs",
    )
    progress_bar_step_name: Optional[FilterTextItemModel] = Field(
        None,
        description="the name of the progress bar step to which the trace step belongs",
    )
    progress_bar_step_position: Optional[FilterItemModel[int]] = Field(
        None,
        description="the position of the progress bar step to which the trace step belongs",
    )
    progress_bar_trace_uid: Optional[FilterTextItemModel] = Field(
        None,
        description="the uid of the progress bar trace to which the trace step belongs",
    )
    uid: Optional[FilterTextItemModel] = Field(
        None,
        description="the primary stable external identifier",
    )
    iterations: Optional[FilterItemModel[Optional[int]]] = Field(
        None,
        description="if the step is iterated, how many iterations were needed for this step in this trace",
    )
    started_at: Optional[FilterItemModel[float]] = Field(
        None,
        description="the time the step began for this trace in seconds since the unix epoch",
    )
    finished_at: Optional[FilterItemModel[float]] = Field(
        None,
        description="the time the step finished for this trace in seconds since the unix epoch",
    )
    duration: Optional[FilterItemModel[float]] = Field(
        None,
        description="the duration of the step for this trace in seconds",
    )
    normalized_duration: Optional[FilterItemModel[float]] = Field(
        None,
        description="the normalized duration of the step for this trace in seconds",
    )


class ReadProgressBarTraceStepRequest(BaseModel):
    filters: Optional[ProgressBarTraceStepFilter] = Field(
        None, description="the filters to apply to the query"
    )
    sort: Optional[List[ProgressBarTraceStepSortOption]] = Field(
        None, description="the sort to apply to the query"
    )
    limit: int = Field(
        100, description="the maximum number of results to return", ge=1, le=100
    )


class ReadProgressBarTraceStepResponse(BaseModel):
    items: List[ProgressBarTraceStep] = Field(
        description="the progress bar trace steps that matched the query"
    )
    next_page_sort: Optional[List[ProgressBarTraceStepSortOption]] = Field(
        description=(
            "if there is a next/previous page of results, "
            "the sort to use to get the next page of results"
        )
    )


@router.post(
    "/search",
    response_model=ReadProgressBarTraceStepResponse,
    responses=STANDARD_ERRORS_BY_CODE,
)
async def read_progress_bar_trace_steps(
    args: ReadProgressBarTraceStepRequest, authorization: Optional[str] = Header(None)
):
    """lists out the steps for a users progress bar trace steps; the user_sub

    filter will be forced to match the authorized user

    This accepts cognito or user token authentication. You can read more about the
    forms of authentication at [/rest_auth.html](/rest_auth.html)
    """
    sort = [srt.to_result() for srt in (args.sort or [])]
    sort = cleanup_sort(PROGRESS_BAR_TRACE_STEP_SORT_OPTIONS, sort, ["uid"])
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
        items = await raw_read_progress_bar_trace_steps(
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
            rev_items = await raw_read_progress_bar_trace_steps(
                itgs, filters_to_apply, rev_sort, 1
            )
            if rev_items:
                first_item = item_pseudocolumns(items[0])

        if first_item is not None or last_item is not None:
            next_page_sort = get_next_page_sort(first_item, last_item, sort)

        return JSONResponse(
            content=ReadProgressBarTraceStepResponse(
                items=items,
                next_page_sort=[s.to_model() for s in next_page_sort]
                if next_page_sort is not None
                else None,
            ).dict()
        )


async def raw_read_progress_bar_trace_steps(
    itgs: Itgs,
    filters_to_apply: List[Tuple[str, Union[FilterItem, FilterTextItem]]],
    sort: List[SortItem],
    limit: int,
) -> List[ProgressBarTraceStep]:
    """performs exactly the specified query without pagination logic"""
    progress_bars = Table("progress_bars")
    progress_bar_steps = Table("progress_bar_steps")
    progress_bar_traces = Table("progress_bar_traces")
    progress_bar_trace_steps = Table("progress_bar_trace_steps")
    users = Table("users")

    query: QueryBuilder = (
        Query.from_(progress_bar_trace_steps)
        .select(
            users.sub,
            progress_bars.name,
            progress_bar_steps.name,
            progress_bar_steps.position,
            progress_bar_traces.uid,
            progress_bar_trace_steps.uid,
            progress_bar_trace_steps.iterations,
            progress_bar_trace_steps.started_at,
            progress_bar_trace_steps.finished_at,
        )
        .join(progress_bar_steps)
        .on(progress_bar_steps.id == progress_bar_trace_steps.progress_bar_step_id)
        .join(progress_bars)
        .on(progress_bars.id == progress_bar_steps.progress_bar_id)
        .join(users)
        .on(users.id == progress_bars.user_id)
        .join(progress_bar_traces)
        .on(progress_bar_traces.id == progress_bar_trace_steps.progress_bar_trace_id)
    )
    qargs = []

    def pseudocolumn(key: str) -> Term:
        if key == "user_sub":
            return users.sub
        elif key == "progress_bar_name":
            return progress_bars.name
        elif key == "progress_bar_step_name":
            return progress_bar_steps.name
        elif key == "progress_bar_step_position":
            return progress_bar_steps.position
        elif key == "progress_bar_trace_uid":
            return progress_bar_traces.uid
        elif key in ("uid", "iterations", "started_at", "finished_at"):
            return progress_bar_trace_steps.field(key)
        elif key == "duration":
            return (
                progress_bar_trace_steps.finished_at
                - progress_bar_trace_steps.started_at
            )
        elif key == "normalized_duration":
            return (
                progress_bar_trace_steps.finished_at
                - progress_bar_trace_steps.started_at
            ) / Coalesce(progress_bar_trace_steps.iterations, 1)
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
    items: List[ProgressBarTraceStep] = []
    for row in response.results or []:
        items.append(
            ProgressBarTraceStep(
                user_sub=row[0],
                progress_bar_name=row[1],
                progress_bar_step_name=row[2],
                progress_bar_step_position=row[3],
                progress_bar_trace_uid=row[4],
                uid=row[5],
                iterations=row[6],
                started_at=row[7],
                finished_at=row[8],
                duration=row[8] - row[7],
                normalized_duration=(row[8] - row[7]) / (row[6] or 1),
            )
        )
    return items


def item_pseudocolumns(item: ProgressBarTraceStep) -> dict:
    """returns the dictified item such that the keys in the return dict match
    the keys of the sort options"""
    result = item.dict()
    result["duration"] = result["finished_at"] - result["started_at"]
    result["normalized_duration"] = result["duration"] / result.get("iterations", 1)
    return result
