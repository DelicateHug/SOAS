"""Wrapper for sensitive values that masks on str/repr/format.

Use .unwrap() to access the real value when needed (e.g., HTTP headers, API calls).
"""


class SensitiveValue:
    """A value wrapper that prints as '***' but preserves the real value internally."""

    __slots__ = ("_value",)

    def __init__(self, value):
        self._value = value

    def unwrap(self):
        """Return the real underlying value."""
        return self._value

    def __str__(self):
        return "***"

    def __repr__(self):
        return "'***'"

    def __format__(self, format_spec):
        return "***"

    def __eq__(self, other):
        if isinstance(other, SensitiveValue):
            return self._value == other._value
        return self._value == other

    def __hash__(self):
        return hash(self._value)

    def __bool__(self):
        return bool(self._value)

    def __len__(self):
        return len(self._value)

    def __contains__(self, item):
        return item in self._value

    def __getitem__(self, key):
        result = self._value[key]
        if isinstance(result, str):
            return SensitiveValue(result)
        return result

    def __iter__(self):
        for ch in self._value:
            yield SensitiveValue(ch)

    def __add__(self, other):
        other_val = other.unwrap() if isinstance(other, SensitiveValue) else other
        return SensitiveValue(self._value + other_val)

    def __radd__(self, other):
        other_val = other.unwrap() if isinstance(other, SensitiveValue) else other
        return SensitiveValue(other_val + self._value)
