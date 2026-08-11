"""
MOEX ISS bond data fetcher.

Загружает параметры облигаций из публичного API Московской биржи:
  https://iss.moex.com/iss/

Основная функция: fetch_bond_params(isins) → pd.DataFrame
  Колонки: ISIN, Duration, Yield, Maturity, Coupon, Name
  Duration — дюрация Маколея в годах.

Логика получения дюрации:
  1. Быстрый путь: берём DURATION из текущих рыночных данных (TQCB/TQOB/TQOD).
  2. Резервный путь: если бумага не торгуется сегодня — считаем дюрацию
     из денежных потоков (bondization endpoint) и последней известной доходности.
"""

from __future__ import annotations

import datetime
import logging
import time
from typing import Optional

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

_BASE = "https://iss.moex.com/iss"
_BOARDS = ["TQCB", "TQOB", "TQOD", "TQOE"]   # корп., ОФЗ, субфед., еврооблиг.
_TIMEOUT = 15
_RETRY   = 2


# ── HTTP-хелпер ───────────────────────────────────────────────────────────────

def _get(url: str, params: dict | None = None) -> dict:
    params = params or {}
    params.setdefault("iss.meta", "off")
    for attempt in range(_RETRY + 1):
        try:
            r = requests.get(url, params=params, timeout=_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            if attempt == _RETRY:
                raise
            logger.warning("ISS request failed (%s), retry %d…", exc, attempt + 1)
            time.sleep(1)


# ── Получение текущих рыночных данных по всем досками ────────────────────────

def _fetch_board(board: str) -> pd.DataFrame:
    """Все бумаги одной доски с дюрацией из текущих рыночных данных."""
    url = f"{_BASE}/engines/stock/markets/bonds/boards/{board}/securities.json"
    data = _get(url, {
        "securities.columns": "SECID,ISIN,SECNAME,MATDATE,COUPONPERCENT,COUPONPERIOD,FACEUNIT",
        "marketdata.columns": "SECID,DURATION,YIELD",
        "iss.only": "securities,marketdata",
    })

    sec = pd.DataFrame(
        data["securities"]["data"],
        columns=data["securities"]["columns"],
    )
    mkt = pd.DataFrame(
        data["marketdata"]["data"],
        columns=data["marketdata"]["columns"],
    )

    if sec.empty:
        return pd.DataFrame()

    mkt = mkt.rename(columns={"DURATION": "_DUR", "YIELD": "_YLD"})
    merged = sec.merge(mkt[["SECID", "_DUR", "_YLD"]], on="SECID", how="left")

    # У части бумаг ISIN отличается от SECID (старые ОФЗ SU...) —
    # для них подтягиваем ISIN через поиск только если ISIN пустой
    merged["ISIN"] = merged["ISIN"].fillna(merged["SECID"])

    merged["Duration"] = pd.to_numeric(merged["_DUR"], errors="coerce") / 365.0
    merged["Yield"]    = pd.to_numeric(merged["_YLD"], errors="coerce")
    merged["board"]    = board
    return merged[["ISIN", "SECID", "SECNAME", "MATDATE", "COUPONPERCENT", "COUPONPERIOD",
                   "FACEUNIT", "Duration", "Yield", "board"]]


def _fetch_all_boards() -> pd.DataFrame:
    frames = []
    for board in _BOARDS:
        try:
            df = _fetch_board(board)
            if not df.empty:
                frames.append(df)
        except Exception as exc:
            logger.warning("Board %s failed: %s", board, exc)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    # Если бумага есть на нескольких досках — берём запись с дюрацией
    combined = combined.sort_values("Duration", na_position="last")
    return combined.drop_duplicates(subset="ISIN", keep="first")


# ── Расчёт дюрации из денежных потоков (резервный путь) ──────────────────────

def _macaulay_from_cashflows(isin: str, yield_annual: Optional[float]) -> Optional[float]:
    """
    Рассчитывает дюрацию Маколея из расписания купонов/амортизаций MOEX ISS.
    yield_annual — годовая доходность (доля, напр. 0.18). Если None — используем купон.
    """
    try:
        data = _get(f"{_BASE}/securities/{isin}/bondization.json")
    except Exception:
        return None

    coupons = pd.DataFrame(
        data.get("coupons", {}).get("data", []),
        columns=data.get("coupons", {}).get("columns", []),
    )
    amortz = pd.DataFrame(
        data.get("amortizations", {}).get("data", []),
        columns=data.get("amortizations", {}).get("columns", []),
    )

    today = datetime.date.today()

    # Будущие купоны
    flows = []
    if not coupons.empty and "coupondate" in coupons.columns:
        coupons["coupondate"] = pd.to_datetime(coupons["coupondate"]).dt.date
        coupons["value_rub"] = pd.to_numeric(coupons.get("value_rub", 0), errors="coerce").fillna(0)
        for _, row in coupons[coupons["coupondate"] > today].iterrows():
            t = (row["coupondate"] - today).days / 365.0
            flows.append((t, float(row["value_rub"])))

    # Будущие амортизации (включая погашение)
    if not amortz.empty and "amortdate" in amortz.columns:
        amortz["amortdate"] = pd.to_datetime(amortz["amortdate"]).dt.date
        amortz["value_rub"] = pd.to_numeric(amortz.get("value_rub", 0), errors="coerce").fillna(0)
        for _, row in amortz[amortz["amortdate"] > today].iterrows():
            t = (row["amortdate"] - today).days / 365.0
            flows.append((t, float(row["value_rub"])))

    if not flows:
        return None

    # Если нет доходности — используем среднюю ставку купона или 15%
    y = yield_annual if yield_annual and not np.isnan(yield_annual) else 0.15

    pv_total  = sum(cf / (1 + y) ** t for t, cf in flows)
    if pv_total <= 0:
        return None
    duration = sum(t * cf / (1 + y) ** t for t, cf in flows) / pv_total
    return round(duration, 4)


# ── Основная функция ──────────────────────────────────────────────────────────

def fetch_bond_params(isins: list[str]) -> pd.DataFrame:
    """
    Возвращает DataFrame с параметрами облигаций для переданных ISINs.

    Колонки:
      ISIN, Name, Maturity, Coupon_pct, Duration, Yield, source

    Duration — дюрация Маколея в годах.
    source   — 'market' | 'floater' (ОФЗ-ПК, dur=0.25y) | 'calculated' | 'not_found'
    """
    isins = [i.strip().upper() for i in isins]

    print("  Загружаем рыночные данные MOEX ISS…")
    all_bonds = _fetch_all_boards()

    results = []
    missing = []

    for isin in isins:
        if not all_bonds.empty and isin in all_bonds["ISIN"].values:
            row = all_bonds[all_bonds["ISIN"] == isin].iloc[0]
            dur = row["Duration"]
            if pd.notna(dur) and dur > 0:
                results.append({
                    "ISIN":       isin,
                    "Name":       row["SECNAME"],
                    "Maturity":   row["MATDATE"],
                    "Coupon_pct": row["COUPONPERCENT"],
                    "Duration":   round(float(dur), 4),
                    "Yield":      row["Yield"],
                    "source":     "market",
                })
                continue
            # ОФЗ-ПК и другие флоатеры: MOEX ставит DURATION=0.
            # Их процентный риск минимален — ставка сбрасывается каждые 6 мес.
            # Используем 0.25 года как консервативную оценку до следующего сброса.
            is_floater = (
                pd.notna(row["SECID"]) and str(row["SECID"]).startswith("SU290")
                or str(row.get("SECNAME", "")).upper().__contains__("-ПК")
            )
            if pd.notna(dur) and dur == 0 and is_floater:
                results.append({
                    "ISIN":       isin,
                    "Name":       row["SECNAME"],
                    "Maturity":   row["MATDATE"],
                    "Coupon_pct": row["COUPONPERCENT"],
                    "Duration":   0.25,
                    "Yield":      row["Yield"],
                    "source":     "floater",
                })
                continue
            # Бумага найдена, но дюрация отсутствует в текущих данных
            missing.append((isin, row["Yield"]))
        else:
            missing.append((isin, None))

    # Резервный путь для недостающих
    if missing:
        print(f"  Считаем дюрацию из денежных потоков для {len(missing)} бумаг…")
        for isin, yield_val in missing:
            y = float(yield_val) / 100.0 if pd.notna(yield_val) and yield_val else None
            dur = _macaulay_from_cashflows(isin, y)
            time.sleep(0.1)   # вежливый rate-limit

            # Имя из all_bonds если есть
            name, maturity, coupon = None, None, None
            if not all_bonds.empty and isin in all_bonds["ISIN"].values:
                r = all_bonds[all_bonds["ISIN"] == isin].iloc[0]
                name    = r["SECNAME"]
                maturity = r["MATDATE"]
                coupon  = r["COUPONPERCENT"]

            results.append({
                "ISIN":       isin,
                "Name":       name,
                "Maturity":   maturity,
                "Coupon_pct": coupon,
                "Duration":   dur,
                "Yield":      float(yield_val) if pd.notna(yield_val) and yield_val else None,
                "source":     "calculated" if dur else "not_found",
            })

    df = pd.DataFrame(results, columns=["ISIN","Name","Maturity","Coupon_pct","Duration","Yield","source"])
    return df.set_index("ISIN")
