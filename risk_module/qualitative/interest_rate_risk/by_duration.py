from __future__ import annotations

import datetime
import pathlib
from typing import Optional, Dict, Any, List

import numpy as np
import pandas as pd
import yaml
from importlib.resources import files

from risk_module.core.models import Portfolio, ComponentResult
from risk_module.data.moex_iss import fetch_bond_params


# ---------------------------------------------------------------------------
# Математика: дюрация, цена, выпуклость
# ---------------------------------------------------------------------------

def _macaulay_duration(c: float, y: float, m: int, n: int) -> float:
    """
    Дюрация Маколея (в годах).

    c — ставка купона за период (coupon_annual / frequency)
    y — доходность за период (yield_annual / frequency)
    m — количество выплат в год
    n — общее количество периодов
    """
    return ((1 + y) / (m * y)) - (
        (1 + y + n * (c - y)) / ((m * c * ((1 + y) ** n - 1)) + m * y)
    )


def _bond_price(c: float, y: float, n: int) -> float:
    """Цена облигации (номинал = 1). c и y — за период."""
    pv_coupons = c * (1 - (1 + y) ** -n) / y
    pv_face = (1 + y) ** -n
    return pv_coupons + pv_face


def _convexity(c: float, y: float, m: int, n: int) -> float:
    """Выпуклость облигации. c и y — за период."""
    price = _bond_price(c, y, n)
    total = sum(
        ((c if t < n else c + 1.0) * (1 + y) ** -t) * t * (t + 1)
        for t in range(1, n + 1)
    )
    return total / (price * (1 + y) ** 2 * m ** 2)


# ---------------------------------------------------------------------------
# Шкала: эталонные облигации → 7 бинов
# ---------------------------------------------------------------------------

def _load_reference_bonds(yaml_path: Optional[str] = None) -> list[dict]:
    if yaml_path is None:
        yaml_file = files(__package__).joinpath("config/reference_bonds.yaml")
    else:
        yaml_file = pathlib.Path(yaml_path)
    with open(yaml_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["reference_bonds"]


def _build_rating_edges(
    reference_bonds: list[dict],
    settlement: datetime.date,
) -> np.ndarray:
    """
    Вычисляет 8 граничных значений дюрации для шкалы 1–7.
    Использует дюрации эталонных бумаг как равновесные точки распределения.
    """
    durations = []
    for bond in reference_bonds:
        maturity = datetime.date.fromisoformat(bond["maturity"])
        n = int(bond["frequency"] * (maturity - settlement).days / 365)
        if n <= 0:
            continue
        c = bond["coupon"] / bond["frequency"]
        y = bond["yield"] / bond["frequency"]
        dur = _macaulay_duration(c, y, bond["frequency"], n)
        durations.append(dur)

    if not durations:
        raise ValueError("Нет действующих эталонных облигаций на дату расчёта.")

    x = np.sort(durations)
    n_bonds = len(x)
    # Каждая бумага — равный вес в распределении
    cdf = np.linspace(1 / n_bonds, 1.0, n_bonds)
    quantiles = np.linspace(0.0, 1.0, 8)
    edges = np.interp(quantiles, cdf, x, left=x[0], right=x[-1])
    return edges


def _duration_to_rating(duration: float, edges: np.ndarray) -> int:
    for i in range(7):
        if edges[i] <= duration < edges[i + 1]:
            return i + 1
    return 1 if duration <= edges[0] else 7


# ---------------------------------------------------------------------------
# Компонент RiskEngine
# ---------------------------------------------------------------------------

class InterestRateRiskComponent:
    """
    Процентный риск облигационного портфеля.

    Дюрация Маколея берётся из MOEX ISS (автоматически).
    Для бумаг, не найденных на бирже, делается fallback на Excel-базу (db_path).
    Эталонные бумаги для построения шкалы 1–7 задаются в reference_bonds.yaml.
    """

    name = "InterestRateRisk"

    def __init__(
        self,
        db_path: str,
        sheet_name: str = "dataBonds",
        config_yaml_path: Optional[str] = None,
        settlement: Optional[datetime.date] = None,
        use_moex: bool = True,
    ) -> None:
        self.db_path = pathlib.Path(db_path)
        self.sheet_name = sheet_name
        self.reference_bonds = _load_reference_bonds(config_yaml_path)
        self.settlement = settlement or datetime.date.today()
        self.use_moex = use_moex

    def calculate(self, portfolio: Portfolio) -> ComponentResult:
        if not portfolio.holdings:
            return ComponentResult(
                component=self.name,
                rating=1,
                category="qualitative",
                meta={"status": "no_holdings"},
            )

        edges = _build_rating_edges(self.reference_bonds, self.settlement)
        isins = [str(h.isin).strip().upper() for h in portfolio.holdings]

        # Шаг 1: Получаем дюрации из MOEX ISS
        moex_data: pd.DataFrame = pd.DataFrame()
        if self.use_moex:
            try:
                moex_data = fetch_bond_params(isins)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("MOEX ISS недоступен: %s", exc)

        # Шаг 2: Fallback — Excel-база для не найденных в MOEX
        excel_data: Dict[str, float] = {}
        moex_not_found = (
            set(isins) - set(moex_data.index[moex_data["Duration"].notna()])
            if not moex_data.empty else set(isins)
        )
        if moex_not_found and self.db_path.exists():
            excel_data = self._load_excel_durations(moex_not_found)

        weighted_duration = 0.0
        covered_weight = 0.0
        found: List[Dict[str, Any]] = []
        not_found: List[Dict[str, Any]] = []

        for holding in portfolio.holdings:
            isin = str(holding.isin).strip().upper()
            dur: Optional[float] = None
            source = "unknown"

            # Попытка 1: MOEX ISS
            if not moex_data.empty and isin in moex_data.index:
                raw = moex_data.loc[isin, "Duration"]
                if pd.notna(raw):
                    dur = float(raw)
                    source = moex_data.loc[isin, "source"]

            # Попытка 2: Excel
            if dur is None and isin in excel_data:
                dur = excel_data[isin]
                source = "excel"

            if dur is None or np.isnan(dur):
                not_found.append({"isin": isin, "status": "DURATION_MISSING"})
                continue

            weighted_duration += dur * holding.weight
            covered_weight += holding.weight
            found.append({"isin": isin, "weight": holding.weight, "duration": dur, "source": source})

        if covered_weight == 0:
            return ComponentResult(
                component=self.name,
                rating=1,
                category="qualitative",
                meta={"status": "no_durations_found", "not_found": not_found},
            )

        avg_duration = weighted_duration / covered_weight
        rating = _duration_to_rating(avg_duration, edges)

        return ComponentResult(
            component=self.name,
            rating=rating,
            category="qualitative",
            meta={
                "weighted_avg_duration": round(avg_duration, 4),
                "covered_weight": round(covered_weight, 4),
                "uncovered_weight": round(1.0 - covered_weight, 4),
                "rating_edges": [round(e, 4) for e in edges],
                "settlement": str(self.settlement),
                "holdings": found,
                "not_found": not_found,
            },
        )

    def _load_excel_durations(self, isins: set[str]) -> Dict[str, float]:
        try:
            df = pd.read_excel(self.db_path, sheet_name=self.sheet_name)
        except Exception:
            return {}
        if "ISIN" not in df.columns or "Duration" not in df.columns:
            return {}
        df["_ISIN"] = df["ISIN"].astype(str).str.strip().str.upper()
        mask = df["_ISIN"].isin(isins)
        return {
            row["_ISIN"]: float(row["Duration"])
            for _, row in df[mask].iterrows()
            if pd.notna(row.get("Duration"))
        }
