from __future__ import annotations

import numpy as np

from risk_module.core.models import Portfolio, ComponentResult
from risk_module.core.scale import RiskScale


class VaRComponent:
    """
    Исторический Value at Risk на горизонте 1 года.

    Метод:
    1. Считаем дневные доходности из NAV.
    2. VaR (дневной) = percentile(returns, 1 - confidence).
    3. Аннуализируем: VaR_1y = VaR_daily * sqrt(trading_days).
    4. |VaR_1y| → рейтинг 1–7 через RiskScale.

    CVaR (Expected Shortfall) сохраняется в meta для информации,
    но не участвует в рейтинге (можно поменять позже).
    """

    name = "VaR"

    def __init__(
        self,
        confidence: float = 0.95,
        trading_days: int = 252,
        min_observations: int = 30,
    ) -> None:
        self.confidence = confidence
        self.trading_days = trading_days
        self.min_observations = min_observations

    def calculate(self, portfolio: Portfolio) -> ComponentResult:
        returns = (
            portfolio.nav_series
            .sort_index()
            .pct_change()
            .dropna()
        )

        if len(returns) < self.min_observations:
            raise ValueError(
                f"[VaR] Недостаточно наблюдений: {len(returns)} < {self.min_observations}. "
                f"Проверь nav_series для {portfolio.identifier}."
            )

        # Исторический VaR (дневной, отрицательное число)
        var_daily = float(np.percentile(returns, (1 - self.confidence) * 100))

        # CVaR — среднее по хвосту левее VaR
        tail = returns[returns < var_daily]
        cvar_daily = float(tail.mean()) if not tail.empty else var_daily

        # Аннуализация по правилу √T
        var_annual = var_daily * np.sqrt(self.trading_days)
        cvar_annual = cvar_daily * np.sqrt(self.trading_days)

        loss_pct = abs(var_annual)
        rating = RiskScale.loss_to_rating(loss_pct)

        return ComponentResult(
            component=self.name,
            rating=rating,
            category="quantitative",
            loss_pct=loss_pct,
            meta={
                "confidence": self.confidence,
                "n_observations": len(returns),
                "var_daily": round(var_daily, 6),
                "var_annual": round(var_annual, 6),
                "cvar_daily": round(cvar_daily, 6),
                "cvar_annual": round(cvar_annual, 6),
            },
        )
