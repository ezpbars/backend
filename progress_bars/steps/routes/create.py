from typing import Literal
from pydantic import BaseModel, Field


class CreateProgressBarStepRequestItem(BaseModel):
    iterated: int = Field(
        0,
        description="""1 if the step is iterated, i.e., it consists of
  many, identical, smaller steps, 0 for a one-off step, i.e., a step which is
  not repeated. Ignored for the default step""",
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
        75,
        description="""required for non-iterated steps using the
  percentile technique. the percent of samples which should complete faster than
  the predicted amount of time. for example, `25` means a quarter of samples
  complete before the progress bar reaches the end. Typically, a high value,
  such as 90, is chosen, since it's better to surprise the user with a faster
  result, than to annoy them with a slower result.""",
        ge=0,
        le=100,
    )
    iterated_technique: Literal[
        "best_fit.linear",
        "percentile",
        "harmonic_mean",
        "geometric_mean",
        "arithmetic_mean",
    ] = Field(
        "best_fit.linear",
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
    iterated_percentile: int = Field(
        75, description="see one-off percentile", ge=0, le=100
    )


class CreateProgressBarStepResponseItem(BaseModel):
    uid: str = Field(description="the primary stable identifyer for this progress bar")
    name: str = Field(
        description="the human-readable name for identifying this progress bar"
    )
    position: int = Field(
        description="when the step occurs within the overall task, i.e., 1 is the first step. The default step has a position of 0",
    )
    iterated: int = Field(
        description="""1 if the step is iterated, i.e., it consists of
  many, identical, smaller steps, 0 for a one-off step, i.e., a step which is
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
