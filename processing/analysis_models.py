"""Validated, versioned configuration shared by query and saved-view APIs."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Filter(StrictModel):
    field: str = Field(max_length=60)
    op: Literal["eq", "ne", "contains", "gt", "gte", "lt", "lte", "empty"] = "eq"
    value: Annotated[str, Field(max_length=1000)] | float | None = None


class FilterGroup(StrictModel):
    join: Literal["and", "or"] = "and"
    rules: list[Filter] = Field(default_factory=list, max_length=20)


class Formula(StrictModel):
    key: str = Field(pattern=r"^calc_[a-zA-Z0-9_]{1,40}$")
    label: str = Field(min_length=1, max_length=100)
    expression: str = Field(min_length=1, max_length=500)
    scope: Literal["row", "group"] = "row"


class Appearance(StrictModel):
    color: str = Field(default="#447869", pattern=r"^#[0-9a-fA-F]{6}$")
    legend: bool = True
    labels: bool = False
    x_label: str = Field(default="", max_length=100)
    y_label: str = Field(default="", max_length=100)
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None
    x_tick_interval: float | None = Field(default=None, gt=0)
    y_tick_interval: float | None = Field(default=None, gt=0)
    x_tick_unit: Literal["day", "hour", "minute", "second"] = "day"
    sort: Literal["x_asc", "x_desc", "y_desc", "y_asc"] = "x_asc"

    @model_validator(mode="after")
    def check_range(self):
        if (
            self.x_min is not None
            and self.x_max is not None
            and self.x_min >= self.x_max
        ):
            raise ValueError("横軸の最小値は最大値より小さくしてください")
        if (
            self.y_min is not None
            and self.y_max is not None
            and self.y_min >= self.y_max
        ):
            raise ValueError("縦軸の最小値は最大値より小さくしてください")
        return self


class TableSort(StrictModel):
    field: str = Field(max_length=60)
    desc: bool = False


class Panel(StrictModel):
    id: str = Field(default="panel_1", max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    title: str = Field(default="キャラクター別の成績", max_length=120)
    chart: Literal[
        "table", "line", "bar", "pie", "box", "histogram", "scatter"
    ] = "line"
    source: Literal["artworks", "snapshots", "followers"] = "artworks"
    stage: str = Field(default="24h", max_length=10)
    x: str = Field(default="character", max_length=60)
    y: list[str] = Field(default_factory=lambda: ["likes"], min_length=1, max_length=6)
    series: str = Field(default="", max_length=60)
    aggregate: Literal["sum", "mean", "median", "min", "max", "count"] = "mean"
    allocation: Literal["full", "split", "combination"] = "full"
    period_days: int = Field(default=0, ge=0, le=3660)
    from_date: str = Field(default="", max_length=10)
    to_date: str = Field(default="", max_length=10)
    filters: list[FilterGroup] = Field(default_factory=list, max_length=10)
    filter_join: Literal["and", "or"] = "and"
    formulas: list[Formula] = Field(default_factory=list, max_length=10)
    transform: Literal["none", "delta", "rate", "moving_average"] = "none"
    window: int = Field(default=7, ge=2, le=100)
    compare_previous: bool = False
    bins: int = Field(default=12, ge=2, le=80)
    show_images: bool = True
    columns: list[str] = Field(
        default_factory=lambda: [
            "title",
            "date",
            "character",
            "likes",
            "retweets",
            "impressions",
        ],
        max_length=25,
    )
    table_sort: str = Field(default="date", max_length=60)
    table_desc: bool = True
    table_sorts: list[TableSort] | None = Field(default=None, max_length=5)
    table_group: str = Field(default="", max_length=60)
    table_group_order: Literal["asc", "desc"] = "asc"
    table_group_dates: Literal["day", "week", "month", "year", "exact"] = "day"
    table_group_multivalue: Literal["individual", "combination"] = "individual"
    table_collapsed_groups: list[Annotated[str, Field(max_length=5000)]] = Field(
        default_factory=list, max_length=2000
    )
    style: Appearance = Field(default_factory=Appearance)


class ViewConfig(StrictModel):
    version: Literal[1] = 1
    layout: Literal["single", "dashboard"] = "single"
    panels: list[Panel] = Field(
        default_factory=lambda: [Panel()], min_length=1, max_length=12
    )

    @model_validator(mode="after")
    def unique_panels(self):
        if len({panel.id for panel in self.panels}) != len(self.panels):
            raise ValueError("パネルIDが重複しています")
        return self


class ViewCreate(StrictModel):
    name: str = Field(default="新しいビュー", min_length=1, max_length=100)
    config: ViewConfig = Field(default_factory=ViewConfig)


class ViewUpdate(ViewCreate):
    revision: int = Field(ge=1)


class ViewLockUpdate(StrictModel):
    locked: bool
    revision: int = Field(ge=1)
