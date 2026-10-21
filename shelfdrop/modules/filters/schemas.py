"""Request and response schemas of the filters module."""

from pydantic import BaseModel, ConfigDict, Field

from shelfdrop.works.types import Kind


class FilterRuleBody(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(min_length=1, max_length=100)
    # Comma-separated words (whole words, any case), or a regular expression when `regex`.
    pattern: str = Field(min_length=1, max_length=500)
    regex: bool
    # Points, positive or negative.
    score: int = Field(ge=-10000, le=10000)
    # The kinds it applies to; empty: every kind.
    kinds: list[Kind] = Field(default_factory=list, max_length=3)
    enabled: bool = True


class FiltersBody(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # In their order.
    rules: list[FilterRuleBody] = Field(max_length=200)
    # A release under this score is set aside.
    minimum: int = Field(ge=-100000, le=100000)
