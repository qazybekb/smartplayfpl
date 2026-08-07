from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence


VariantName = Literal["optimal", "no_hits", "hit_1", "roll"] | str


@dataclass(frozen=True)
class SolveContext:
    run_id: str | None
    current_gw: int
    horizon: int


@dataclass(frozen=True)
class TeamPick:
    element: int
    selling_price: int  # tenths
    purchase_price: int  # tenths
    multiplier: int
    is_captain: bool
    is_vice_captain: bool


@dataclass(frozen=True)
class TeamTransfers:
    bank: int  # tenths
    limit: int | None
    made: int
    cost: int
    status: str


@dataclass(frozen=True)
class TeamChip:
    name: str
    status_for_entry: str


@dataclass(frozen=True)
class TeamJson:
    picks: Sequence[Mapping[str, Any]]
    transfers: Mapping[str, Any]
    chips: Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class SolverOptions:
    # Core
    horizon: int = 3
    objective: str = "decay"
    decay_base: float = 0.9
    secs: int = 60
    gap: float = 0.01

    # Values / tuning
    hit_cost: float = 4.0
    vcap_weight: float = 0.1
    itb_value: float = 0.02
    bench_weights: Mapping[int, float] | None = None
    ft_value_list: Mapping[str, float] | None = None
    ft_value: float = 1.5

    # Pool filters
    xmin_lb: int = 100
    keep_top_ev_percent: float = 10.0
    ev_per_price_cutoff: float = 0.0

    # Constraints and controls
    banned: Sequence[int] | None = None
    locked: Sequence[int] | None = None
    booked_transfers: Sequence[Mapping[str, Any]] | None = None
    only_booked_transfers: bool = False
    no_future_transfer: bool = False
    no_transfer_gws: Sequence[int] | None = None
    no_transfer_last_gws: int | None = None

    weekly_hit_limit: int | None = 0
    hit_limit: int | None = 0

    chip_limits: Mapping[str, int] | None = None
    forced_chip_gws: Mapping[str, Sequence[int]] | None = None

    # UX forcing (Phase 4b; optional)
    allow_hits: bool | None = None
    min_transfers: int | None = None
    force_variant: str | None = None

