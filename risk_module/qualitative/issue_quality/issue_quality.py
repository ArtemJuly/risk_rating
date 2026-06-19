from __future__ import annotations

import pathlib
from typing import Optional, Dict, Any, List

import pandas as pd

from risk_module.core.models import Portfolio, ComponentResult


# ---------------------------------------------------------------------------
# Rating logic (vectorized, operates on full Excel)
# ---------------------------------------------------------------------------

_QUASI_SOVEREIGN = (
    "газпром|ржд|роснефть|сбербанк|сибур|втб|сбер|газпром капитал|минфин россии"
)
_LARGE_CORP = "лукойл|норникель|новатэк|нлмк|северсталь|русал|магнит|x5|альфа-банк"
_MID_CORP = "полюс|мтс|фосагро|совкомфлот|транснефть"
_SMALL_HY = "пик|самолет|фск|lenta|озон|о'кей"


def _rating_quality(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)

    issuer = df["Эмитент"].astype(str).str.strip().str.lower()
    main_borrower = (
        df.get("Основной заемщик", pd.Series([""] * len(df)))
        .astype(str).str.strip().str.lower()
    )
    valuta = (
        df.get("Валюта номинала", pd.Series(["RUB"] * len(df)))
        .astype(str).str.strip()
    )
    subord = (
        df.get("Субординированная (да/нет)", pd.Series(["нет"] * len(df)))
        .astype(str).str.strip().str.lower()
    )
    years_to_mat = df.get("Лет до даты", 0).fillna(0)
    credit_quality = df.get("Качество эмитента (max=10)", 5).fillna(5)

    rating = pd.Series(0, index=df.index, dtype=int)

    def _contains(series, pattern):
        return series.str.contains(pattern, case=False, na=False, regex=True)

    # 1 – квазисуверенные
    quasi_mask = _contains(issuer, _QUASI_SOVEREIGN) | _contains(main_borrower, _QUASI_SOVEREIGN)
    rating[quasi_mask] = 1

    # 2 – крупные IG
    large_mask = _contains(issuer, _LARGE_CORP) | _contains(main_borrower, _LARGE_CORP)
    rating[(rating == 0) & large_mask] = 2

    # 3 – средние BBB
    mid_mask = _contains(issuer, _MID_CORP) | _contains(main_borrower, _MID_CORP)
    rating[(rating == 0) & mid_mask] = 3

    # 4 – еврооблигации или долгосрочные (>5 лет)
    euro_long_mask = (valuta != "RUB") | (years_to_mat > 5)
    rating[(rating == 0) & euro_long_mask] = 4

    # 5 – субординированные (перезаписывает)
    sub_mask = _contains(subord, "да")
    rating[sub_mask] = 5

    # 6 – конвертируемые
    conv_mask = _contains(issuer, "конверт")
    rating[(rating == 0) & conv_mask] = 6

    # 7 – high-yield малые
    hy_mask = _contains(issuer, _SMALL_HY) | _contains(main_borrower, _SMALL_HY)
    rating[(rating == 0) & hy_mask] = 7

    # Fallback по качеству эмитента
    fb = rating == 0
    rating[fb & (credit_quality >= 8)] = 2
    rating[fb & (credit_quality >= 6) & (credit_quality < 8)] = 3
    rating[fb & (credit_quality >= 4) & (credit_quality < 6)] = 4
    rating[fb & (credit_quality >= 2) & (credit_quality < 4)] = 6
    rating[fb & (credit_quality < 2)] = 7
    rating[rating == 0] = 7

    df["Рейтинг"] = rating
    return df[["ISIN", "Эмитент", "Рейтинг", "Валюта номинала"]]


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------

class IssueQualityComponent:
    """
    Качество эмитентов облигационного портфеля.

    Логика:
    1. Загружает Excel с данными по бумагам и присваивает рейтинг 1–7
       каждому ISIN через _rating_quality().
    2. Считает взвешенный средний рейтинг по весам из Portfolio.holdings.
    3. Округляет → итоговый рейтинг компонента.
    """

    name = "IssueQuality"

    def __init__(self, db_path: str) -> None:
        self.db_path = pathlib.Path(db_path)

    def calculate(self, portfolio: Portfolio) -> ComponentResult:
        if not portfolio.holdings:
            return ComponentResult(
                component=self.name,
                rating=1,
                category="qualitative",
                meta={"status": "no_holdings"},
            )

        if not self.db_path.exists():
            return ComponentResult(
                component=self.name,
                rating=1,
                category="qualitative",
                meta={"status": "db_not_found", "path": str(self.db_path)},
            )

        ratings_df = _rating_quality(str(self.db_path))
        ratings_df["_ISIN"] = ratings_df["ISIN"].astype(str).str.strip().str.upper()

        weighted_rating = 0.0
        covered_weight = 0.0
        found: List[Dict[str, Any]] = []
        not_found: List[Dict[str, Any]] = []

        for holding in portfolio.holdings:
            isin = str(holding.isin).strip().upper()
            row = ratings_df.loc[ratings_df["_ISIN"] == isin]

            if row.empty:
                not_found.append({"isin": isin, "weight": holding.weight, "status": "NOT_FOUND"})
                continue

            r = int(row.iloc[0]["Рейтинг"])
            weighted_rating += r * holding.weight
            covered_weight += holding.weight
            found.append({
                "isin": isin,
                "weight": holding.weight,
                "issuer": row.iloc[0]["Эмитент"],
                "issue_rating": r,
            })

        if covered_weight == 0:
            return ComponentResult(
                component=self.name,
                rating=7,
                category="qualitative",
                meta={"status": "no_ratings_found", "not_found": not_found},
            )

        avg_rating = weighted_rating / covered_weight
        final_rating = max(1, min(7, round(avg_rating)))

        return ComponentResult(
            component=self.name,
            rating=final_rating,
            category="qualitative",
            meta={
                "weighted_avg_rating": round(avg_rating, 2),
                "covered_weight": round(covered_weight, 4),
                "uncovered_weight": round(1.0 - covered_weight, 4),
                "holdings": found,
                "not_found": not_found,
            },
        )
