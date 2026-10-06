"""
Page-related Pydantic models.

Represent a browser page (tab) state as seen by MCP tools.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PageInfo(BaseModel):
    """Serialisable snapshot of a browser page."""

    page_id: str
    session_id: str
    url: str
    title: str
    is_active: bool = False


class TabsInfo(BaseModel):
    """List of all open pages within a session."""

    session_id: str
    tabs: list[PageInfo] = Field(default_factory=list)
    active_tab_id: str | None = None
    count: int = 0

    def model_post_init(self, __context: object) -> None:
        self.count = len(self.tabs)
