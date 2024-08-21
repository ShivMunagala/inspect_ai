from logging import getLogger
from typing import (
    Any,
    Callable,
    Protocol,
    TypeVar,
    Union,
    cast,
    overload,
    runtime_checkable,
)

from pydantic import BaseModel, Field

from inspect_ai._util.registry import (
    RegistryInfo,
    registry_add,
    registry_create,
    registry_name,
    registry_tag,
)

logger = getLogger(__name__)

CORRECT = "C"
"""Value to assign for correct answers."""

INCORRECT = "I"
"""Value to assign for incorrect answers."""

PARTIAL = "P"
"""Value to assign for partial credit."""

NOANSWER = "N"
"""Value to assign for no answer or refusal to answer."""


Value = Union[
    str | int | float | bool,
    list[str | int | float | bool],
    dict[str, str | int | float | bool | None],
]
"""Value provided by a score.

Use the methods of `Score` to easily treat
the Value as a simple scalar of various types.
"""


class Score(BaseModel):
    """Score generated by a scorer.

    Args:
       value (Value): Score value.
       answer (str | None): Answer extracted from model output (optional).
       explanation (str | None): Explanation of score (optional).
       metadata (dict[str,Any]): Additional metadata related to the score.
    """

    value: Value
    """Score value."""

    answer: str | None = Field(default=None)
    """Answer extracted from model output (optional)"""

    explanation: str | None = Field(default=None)
    """Explanation of score (optional)."""

    metadata: dict[str, Any] | None = Field(default=None)
    """Additional metadata related to the score"""

    @property
    def text(self) -> str:
        """Read the score as text."""
        return self.as_str()

    def as_str(self) -> str:
        """Read the score as a string."""
        return str(self._as_scalar())

    def as_int(self) -> int:
        """Read the score as an integer."""
        return int(self._as_scalar())

    def as_float(self) -> float:
        """Read the score as a float."""
        return float(self._as_scalar())

    def as_bool(self) -> bool:
        """Read the score as a boolean."""
        return bool(self._as_scalar())

    def _as_scalar(self) -> str | int | float | bool:
        if isinstance(self.value, str | int | float | bool):
            return self.value
        else:
            raise ValueError("This score is not a scalar")


class SampleScore(Score):
    """Score for a Sample

    Args:
       sample_id: (str | int | None) Unique id of a sample
    """

    sample_id: str | int | None = Field(default=None)
    """A sample id"""


ValueToFloat = Callable[[Value], float]
"""Function used by metrics to translate from a Score value to a float value."""


def value_to_float(
    correct: Value = CORRECT,
    incorrect: Value = INCORRECT,
    partial: Value = PARTIAL,
    noanswer: Value = NOANSWER,
) -> ValueToFloat:
    """Create a ValueToFloat function.

    Create a ValueToFloat function that maps scalar values of
    different types into floats. For strings, common boolean
    representations (e.g. 'yes', 'no', 'true', 'false') are
    mapped to 1 and 0. In addition, the specified correct,
    incorrect, partial, and noanswer values (by default "C"
    "I", "P", are mapped to "N" to 1, 0, 0.5, and 0. Note that
    those are the default literal values, but they can be
    customized. Strings with only numbers are converted, and
    numeric values are cast to float. Arrays and dictionarie
    give a warning and return 0.

    Args:
       correct (Value): Value that represents a correct answer (1)
       incorrect (Value): Value that represents an incorrect answer (0)
       partial (Value): Value to assign partial credit for (0.5)
       noanswer (Value): Value for refusals to answer (0)

    Returns:
        ValueToFloat function.
    """

    def to_float(value: Value) -> float:
        if isinstance(value, int | float | bool):
            return float(value)
        elif value == correct:
            return 1.0
        elif value == partial:
            return 0.5
        elif value == incorrect or value == noanswer:
            return 0
        elif isinstance(value, str):
            value = value.lower()
            if value in ["yes", "true"]:
                return 1.0
            elif value in ["no", "false"]:
                return 0.0
            elif value.replace(".", "").isnumeric():
                return float(value)

        # couldn't extract a value
        logger.warning(f"Unable to convert value to float: {value}")
        return 0.0

    return to_float


@runtime_checkable
class Metric(Protocol):
    r"""Evaluate scores using a metric.

    Args:
        scores (list[Score]): List of scores.

    Returns:
        Metric value
    """

    def __call__(self, scores: list[Score]) -> Value: ...


MetricType = TypeVar("MetricType", Callable[..., Metric], type[Metric])
r"""Metric type.
Valid metric types include:
 - Functions that return a Metric
 - Classes derived from Metric
"""


def metric_register(metric: MetricType, name: str = "") -> MetricType:
    r"""Register a function or class as a metric.

    Args:
        metric (MetricType):
            Function that returns a Metric or class
            deriving fromMetric
        name (str): Name of metric (Optional, defaults to object name)

    Returns:
        Metric type with registry attributes.
    """
    metric_name = name if name else getattr(metric, "__name__")
    registry_add(metric, RegistryInfo(type="metric", name=metric_name))
    return metric


def metric_create(name: str, **kwargs: Any) -> Metric:
    r"""Create a Metric based on its registered name.

    Metrics can be functions that return a Metric or classes
    deriving from Metric

    Args:
        name (str): Name of metric (Optional, defaults to object name)
        **kwargs (dict): Optional creation arguments for the metric

    Returns:
        Metric with registry info attribute
    """
    return cast(Metric, registry_create("metric", name, **kwargs))


@overload
def metric(name: str) -> Callable[..., MetricType]: ...


@overload
# type: ignore
def metric(name: Callable[..., Metric]) -> Callable[..., Metric]: ...


@overload
def metric(name: type[Metric]) -> type[Metric]: ...


def metric(name: str | MetricType) -> Callable[..., MetricType] | MetricType:
    r"""Decorator for registering metrics.

    Args:
        name: (str | MetricType):
            Optional name for metric. If the decorator has no name
            argument then the name of the underlying MetricType
            will be used to automatically assign a name.
    """

    # create_metric_wrapper:
    #  (a) Add the MetricType to the registry using the appropriately
    #      package-namespaced name
    #  (b) Ensure that instances of Metric created by MetricType also
    #      carry registry info.
    def create_metric_wrapper(
        metric_type: MetricType, name: str | None = None
    ) -> MetricType:
        metric_name = registry_name(
            metric_type, name if name else getattr(metric_type, "__name__")
        )

        def metric_wrapper(*args: Any, **kwargs: Any) -> Metric:
            metric = metric_type(*args, **kwargs)
            registry_tag(
                metric_type,
                metric,
                RegistryInfo(type="metric", name=metric_name),
                *args,
                **kwargs,
            )
            return metric

        return metric_register(cast(MetricType, metric_wrapper), metric_name)

    # for decorators with an explicit name, one more wrapper for the name
    if isinstance(name, str):

        def wrapper(metric_type: MetricType) -> MetricType:
            return create_metric_wrapper(metric_type, name)

        return wrapper

    # create a metric wrapper for the passed metric_type
    else:
        metric_type = name
        return create_metric_wrapper(metric_type)
