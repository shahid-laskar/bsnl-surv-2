"""
app/schemas/common.py
Shared Pydantic V2 schemas: pagination wrapper and error shapes.
"""

import math
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, computed_field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated list response."""

    items: list[T]
    total: int
    page: int
    page_size: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pages(self) -> int:
        """Total number of pages."""
        if self.page_size == 0:
            return 0
        return math.ceil(self.total / self.page_size)


class PaginationParams(BaseModel):
    """Common query parameters for paginated endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-based)")
    page_size: int = Field(default=25, ge=1, le=200, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error response shape returned by the exception handler."""

    error: ErrorDetail


class MessageResponse(BaseModel):
    """Simple success message for operations that don't return data."""

    message: str
