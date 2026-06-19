from __future__ import annotations

import json
import pathlib
from typing import Optional, Dict, Any, List

import numpy as np
import pandas as pd
import yaml
from importlib.resources import files

from risk_module.core.models import Portfolio, ComponentResult


# ---------------------------------------------------------------------------
# Data preprocessing
# ---------------------------------------------------------------------------

def _preprocess(path: str):
    df = pd.read_csv(path, sep=",")
    df["levels"] = df["data"].apply(lambda x: json.loads(x)["levels"])
    df["bestAskPrice"] = df["bestAskPrice"].astype(str).str.replace(",", "").astype(float)
    df["bestBidPrice"] = df["bestBidPrice"].astype(str).str.replace(",", "").astype(float)
    df_exploded = df.explode("levels")
    df_exploded["side"] = df_exploded["levels"].apply(lambda x: x["side"])
    df_exploded["size"] = df_exploded["levels"].apply(lambda x: x["size"])
    df_exploded["price"] = df_exploded["levels"].apply(lambda x: x["price"])
    return df_exploded, df


# ---------------------------------------------------------------------------
# Metric computations (no plotting)
# ---------------------------------------------------------------------------

def _lix(df_exploded: pd.DataFrame, freq: str = "60min") -> float:
    df = df_exploded.copy()
    df["createdAt"] = pd.to_datetime(df["createdAt"])
    grouped = df.groupby(df["createdAt"].dt.floor(freq)).agg(
        avg_ask=("bestAskPrice", "mean"),
        avg_bid=("bestBidPrice", "mean"),
        total_size=("size", "sum"),
        price_high=("price", "max"),
        price_low=("price", "min"),
    ).reset_index()
    grouped["mid_price"] = (grouped["avg_ask"] + grouped["avg_bid"]) / 2
    price_range = grouped["price_high"] - grouped["price_low"]
    mask = price_range > 0
    lix_series = np.log10(
        (grouped.loc[mask, "total_size"] * grouped.loc[mask, "mid_price"]) / price_range[mask]
    )
    return float(lix_series.mean()) if not lix_series.empty else np.nan


def _cost_of_liquidity(df: pd.DataFrame, freq: str = "60min") -> float:
    data = df.copy()
    data["createdAt"] = pd.to_datetime(data["createdAt"])
    data["mid_price"] = (data["bestAskPrice"] + data["bestBidPrice"]) / 2
    data["spread_pct"] = np.where(
        data["mid_price"] > 0,
        ((data["bestAskPrice"] - data["bestBidPrice"]) / data["mid_price"]) * 100,
        np.nan,
    )
    spread_df = (
        data.groupby(data["createdAt"].dt.floor(freq))["spread_pct"]
        .mean()
        .reset_index()
    )
    return float(spread_df["spread_pct"].mean())


def _roll_measure(df: pd.DataFrame, max_lag: int = 1) -> float:
    P = (df["bestAskPrice"] + df["bestBidPrice"]) / 2
    dP = P.diff().dropna()
    if len(dP) < 2:
        return np.nan
    cov = np.cov(dP.iloc[1:], dP.iloc[:-1], bias=True)[0, 1]
    return float(2 * np.sqrt(-cov)) if cov < 0 else 0.0


def _amihud_ratio(df: pd.DataFrame, freq: str = "60min") -> float:
    data = df.copy()
    data["createdAt"] = pd.to_datetime(data["createdAt"])
    data["mid_price"] = (data["bestAskPrice"] + data["bestBidPrice"]) / 2
    data["hour"] = data["createdAt"].dt.floor(freq)
    grouped = data.groupby("hour").agg(
        mid_price=("mid_price", "mean"),
        total_size=("size", "sum"),
    ).reset_index()
    grouped["dollar_volume"] = grouped["mid_price"] * grouped["total_size"]
    grouped["return_abs"] = grouped["mid_price"].pct_change().abs()
    grouped["amihud"] = grouped["return_abs"] / grouped["dollar_volume"]
    return float(grouped["amihud"].mean())


# ---------------------------------------------------------------------------
# Scale loading and rating mapping
# ---------------------------------------------------------------------------

def _load_scale(yaml_path: Optional[str] = None) -> dict:
    if yaml_path is None:
        yaml_file = files(__package__).joinpath("config/liquidity_scale.yaml")
    else:
        yaml_file = pathlib.Path(yaml_path)
    with open(yaml_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _lix_to_rating(value: float, cfg: dict) -> int:
    if np.isnan(value):
        return cfg["fallback_rating"]
    for bucket in cfg["thresholds"]:
        if value >= bucket["min"]:
            return bucket["rating"]
    return cfg["fallback_rating"]


def _threshold_to_rating(value: float, cfg: dict) -> int:
    if np.isnan(value):
        return cfg["fallback_rating"]
    for bucket in cfg["thresholds"]:
        if value <= bucket["max"]:
            return bucket["rating"]
    return cfg["fallback_rating"]


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------

class LiquidityRiskComponent:
    """
    Риск ликвидности на основе данных биржевого стакана (order book CSV).

    Вычисляет четыре метрики:
    - LIX          — индекс ликвидности (выше = ликвиднее)
    - Cost of Liq  — средний bid-ask спред, %
    - Roll Measure — оценка спреда через автоковариацию
    - Amihud Ratio — соотношение доходности к объёму

    Каждая метрика маппится в рейтинг 1–7 через liquidity_scale.yaml.
    Итоговый рейтинг компонента = max из четырёх суб-рейтингов.
    """

    name = "LiquidityRisk"

    def __init__(
        self,
        csv_path: str,
        freq: str = "60min",
        scale_yaml_path: Optional[str] = None,
    ) -> None:
        self.csv_path = pathlib.Path(csv_path)
        self.freq = freq
        self._scale = _load_scale(scale_yaml_path)

    def calculate(self, portfolio: Portfolio) -> ComponentResult:
        if not self.csv_path.exists():
            return ComponentResult(
                component=self.name,
                rating=1,
                category="qualitative",
                meta={"status": "csv_not_found", "path": str(self.csv_path)},
            )

        try:
            df_exploded, df = _preprocess(str(self.csv_path))
        except Exception as exc:
            return ComponentResult(
                component=self.name,
                rating=1,
                category="qualitative",
                meta={"status": "preprocess_error", "error": str(exc)},
            )

        lix_val    = _lix(df_exploded, self.freq)
        col_val    = _cost_of_liquidity(df, self.freq)
        roll_val   = _roll_measure(df)
        amihud_val = _amihud_ratio(df, self.freq)

        lix_r    = _lix_to_rating(lix_val,    self._scale["lix"])
        col_r    = _threshold_to_rating(col_val,    self._scale["cost_of_liquidity"])
        roll_r   = _threshold_to_rating(roll_val,   self._scale["roll"])
        amihud_r = _threshold_to_rating(amihud_val, self._scale["amihud"])

        rating = max(lix_r, col_r, roll_r, amihud_r)

        return ComponentResult(
            component=self.name,
            rating=rating,
            category="qualitative",
            meta={
                "lix":            round(lix_val, 4)    if not np.isnan(lix_val)    else None,
                "cost_of_liq_%":  round(col_val, 6)    if not np.isnan(col_val)    else None,
                "roll_measure":   round(roll_val, 6)   if not np.isnan(roll_val)   else None,
                "amihud_ratio":   amihud_val            if not np.isnan(amihud_val) else None,
                "sub_ratings": {
                    "lix":    lix_r,
                    "col":    col_r,
                    "roll":   roll_r,
                    "amihud": amihud_r,
                },
            },
        )
