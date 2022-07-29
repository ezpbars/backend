"""Standard responses and requests"""

from pydantic import Field, validator
from pydantic.generics import GenericModel
from typing import Generic, TypeVar, Optional

TypeT = TypeVar("TypeT")


class StandardErrorResponse(GenericModel, Generic[TypeT]):
    type: TypeT = Field(
        title="Type",
        description="the type of error that occurred",
    )

    message: str = Field(title="Message", description="a human readable error message")

    markdown: Optional[str] = Field(
        title="Markdown", description="markdown formatted error message"
    )

    @validator("markdown", always=True)
    def set_markdown(cls, v, values, **kwargs):
        if v is not None:
            return v
        return values["message"]
