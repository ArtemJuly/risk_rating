from __future__ import annotations

import pandas as pd
import numpy as np

from risk_module.core.models import Portfolio, ComponentResult
from risk_module.core.scale import RiskScale


def _load_price_series(filepath: str) -> pd.Series:
    df = pd.read_excel(filepath)
    df.columns = df.columns.astype(str).str.strip()
    df["Date"] = pd.to_datetime(df.iloc[:, 0])
    df = df.set_index("Date").sort_index()
    df.index = df.index.normalize()
    series = pd.to_numeric(
        df.iloc[:, 0].astype(str).str.replace(" ", "").str.replace(",", "."),
        errors="coerce",
    )
    return series.dropna()


class BetaStressComponent:
    """
    Бета-факторный стресс-тест.

    Логика:
    1. Считаем бету фонда к выбранному индексу на всём доступном
       пересечении NAV фонда и истории индекса (train-период).
    2. Берём дневные доходности индекса в стресс-периоде.
    3. Масштабируем через бету → получаем прогнозные дневные доходности фонда.
    4. Компаундируем → накопленная доходность → loss_pct → рейтинг 1–7.

    Бета вычисляется как cov(r_fund, r_index) / var(r_index).
    """

    name = "StressTest"

    def __init__(
        self,
        index_file: str,
        stress_start: str,
        stress_end: str,
        index_label: str = "Index",
    ) -> None:
        self.index_file = index_file
        self.stress_start = pd.Timestamp(stress_start).normalize()
        self.stress_end = pd.Timestamp(stress_end).normalize()
        self.index_label = index_label

    def calculate(self, portfolio: Portfolio) -> ComponentResult:
        index = _load_price_series(self.index_file)

        fund = portfolio.nav_series.copy()
        fund.index = pd.DatetimeIndex(fund.index).normalize()

        # --- Дневные доходности на train-периоде (пересечение фонда и индекса) ---
        train = (
            pd.concat([fund.rename("Fund"), index.rename("Index")], axis=1)
            .dropna()
            .pct_change()
            .dropna()
        )

        if len(train) < 30:
            raise ValueError(
                f"[BetaStress] Недостаточно пересекающихся наблюдений: {len(train)}. "
                f"Проверь nav_series и index_file для {portfolio.identifier}."
            )

        # --- Бета ---
        cov = train["Fund"].cov(train["Index"])
        var = train["Index"].var()
        beta = cov / var

        # --- Дневные доходности индекса в стресс-периоде ---
        stress_index = (
            index.loc[self.stress_start:self.stress_end]
            .pct_change()
            .dropna()
        )

        if stress_index.empty:
            raise ValueError(
                f"[BetaStress] Нет данных индекса в стресс-периоде "
                f"{self.stress_start.date()} – {self.stress_end.date()}."
            )

        # --- Прогнозные доходности фонда = beta × index_daily ---
        stress_fund = beta * stress_index

        cum_return = float((1 + stress_fund).prod() - 1)
        cum_prod = (1 + stress_fund).cumprod()
        max_drawdown = float((cum_prod / cum_prod.cummax() - 1).min())

        loss_pct = abs(min(0.0, cum_return))
        rating = RiskScale.loss_to_rating(loss_pct)

        # Шок индекса за стресс-период (для контекста)
        index_shock = float((1 + stress_index).prod() - 1)

        return ComponentResult(
            component=self.name,
            rating=rating,
            category="quantitative",
            loss_pct=loss_pct,
            meta={
                "index": self.index_label,
                "beta": round(beta, 4),
                "stress_start": str(self.stress_start.date()),
                "stress_end": str(self.stress_end.date()),
                "index_shock": round(index_shock, 6),
                "fund_stress_return": round(cum_return, 6),
                "max_drawdown": round(max_drawdown, 6),
                "n_train": len(train),
                "n_stress": len(stress_index),
            },
        )
