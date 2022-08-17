from enum import Enum


class StandardOperator(str, Enum):
    """Describes a standard operator that can be applied to a comparable type."""
    EQUAL = 'eq'
    NOT_EQUAL = 'neq'
    GREATER_THAN = 'gt'
    GREATER_THAN_OR_EQUAL = 'gte'
    LESS_THAN = 'lt'
    LESS_THAN_OR_EQUAL = 'lte'
