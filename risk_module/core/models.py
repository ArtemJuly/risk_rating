from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import pandas as pd


@dataclass
class Holding:
    isin: str
    weight: float  # 0.0–1.0


@dataclass
class Portfolio:
    identifier: str          # ISIN фонда
    nav_series: pd.Series    # индекс — дата, значения — цены NAV
    holdings: list[Holding] = field(default_factory=list)


@dataclass
class ComponentResult:
    component: str                    # "VaR", "StressTest", "CreditRisk"
    rating: int                       # 1–7
    category: str = ""                # "quantitative" | "qualitative"
    loss_pct: Optional[float] = None  # ожидаемый максимальный убыток, 0.0–1.0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskResult:
    identifier: str
    final_rating: int
    components: list[ComponentResult] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "identifier": self.identifier,
            "final_rating": self.final_rating,
            "components": [
                {
                    "component": r.component,
                    "rating": r.rating,
                    "loss_pct": round(r.loss_pct * 100, 2) if r.loss_pct is not None else None,
                }
                for r in self.components
            ],
        }
