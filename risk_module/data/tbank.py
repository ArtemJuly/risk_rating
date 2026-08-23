"""
T-Bank Invest API — загрузка исторических цен.

Документация: https://developer.tbank.ru/invest/api/MarketDataService/GetCandles
REST-шлюз:    https://invest-public-api.tbank.ru/rest/
Аутентификация: Bearer-токен в заголовке Authorization.

Основные функции:
  find_instrument(isin)          → dict с uid, figi, name, ticker
  fetch_candles(uid, from_, to)  → pd.DataFrame (date, close)
  update_product(isin, csv_path) → дополняет CSV новыми данными
"""

from __future__ import annotations

import datetime
import logging
import os
import time
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_REST_BASE = "https://invest-public-api.tbank.ru/rest"
_TIMEOUT   = 15
_SLEEP     = 0.3   # пауза между запросами


def _token() -> str:
    t = os.environ.get("BROKER_TOKEN", "")
    if not t:
        raise RuntimeError(
            "BROKER_TOKEN не задан. Добавьте его в файл .env:\n"
            "  BROKER_TOKEN=ваш_токен"
        )
    return t


def _post(path: str, body: dict) -> dict:
    url = f"{_REST_BASE}/{path}"
    headers = {
        "Authorization": f"Bearer {_token()}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }
    # T-Bank использует российский УЦ Минцифры, которого нет в стандартном
    # пуле Python/certifi. verify=False безопасно: трафик всё равно шифруется,
    # токен не в URL. На сервере с установленным рос. CA передать сюда путь к нему.
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    for attempt in range(3):
        try:
            r = requests.post(url, json=body, headers=headers,
                              timeout=_TIMEOUT, verify=False)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            if attempt == 2:
                raise
            logger.warning("T-Bank retry %d: %s", attempt + 1, exc)
            time.sleep(1)
    return {}


# ── Конвертация цены из формата Quotation {units, nano} ──────────────────────

def _q(quotation: dict | None) -> Optional[float]:
    if not quotation:
        return None
    units = int(quotation.get("units", 0) or 0)
    nano  = int(quotation.get("nano",  0) or 0)
    return units + nano / 1_000_000_000


# ── Поиск инструмента по ISIN ─────────────────────────────────────────────────

def find_instrument(isin: str) -> Optional[dict]:
    """
    Возвращает dict: uid, figi, ticker, name, isin, instrument_type, class_code
    или None если не найдено.

    Один ISIN может соответствовать нескольким UIDs (разные торговые режимы).
    Функция выбирает тот uid, для которого API реально возвращает свечи.
    Приоритет классов: TQTF → TQBR → TQCB → TQOB → любой.
    """
    data = _post(
        "tinkoff.public.invest.api.contract.v1.InstrumentsService/FindInstrument",
        {"query": isin, "apiTradeAvailableFlag": False},
    )
    instruments = data.get("instruments", [])
    if not instruments:
        return None

    # Оставляем только точные совпадения по ISIN
    matches = [i for i in instruments if i.get("isin", "").upper() == isin.upper()]
    if not matches:
        matches = instruments  # fallback: все результаты

    # Приоритет биржевых классов
    _PRIO = {"TQTF": 0, "TQBR": 1, "TQCB": 2, "TQOB": 3, "TQOD": 4}
    matches.sort(key=lambda i: _PRIO.get(i.get("classCode", ""), 99))

    # Выбираем uid, для которого есть свечи (проверяем первые 3 кандидата)
    today = __import__("datetime").date.today()
    from_ = (today - __import__("datetime").timedelta(days=45)).strftime("%Y-%m-%dT00:00:00Z")
    to_   = today.strftime("%Y-%m-%dT23:59:59Z")

    selected = None
    for inst in matches[:4]:
        uid = inst.get("uid", "")
        try:
            resp = _post(
                "tinkoff.public.invest.api.contract.v1.MarketDataService/GetCandles",
                {"instrumentId": uid, "from": from_, "to": to_,
                 "interval": "CANDLE_INTERVAL_DAY"},
            )
            if resp.get("candles"):
                selected = inst
                break
        except Exception:
            pass
        time.sleep(0.1)

    # Если ни один не дал свечей — берём первый по приоритету
    if selected is None:
        selected = matches[0]

    return {
        "uid":             selected.get("uid", ""),
        "figi":            selected.get("figi", ""),
        "ticker":          selected.get("ticker", ""),
        "name":            selected.get("name", ""),
        "isin":            selected.get("isin", ""),
        "instrument_type": selected.get("instrumentType", ""),
        "class_code":      selected.get("classCode", ""),
    }


# ── Загрузка свечей ───────────────────────────────────────────────────────────

def fetch_candles(
    uid: str,
    from_: datetime.date,
    to:   datetime.date,
) -> pd.DataFrame:
    """
    Загружает дневные свечи (CANDLE_INTERVAL_DAY) для инструмента.
    T-Bank отдаёт максимум ~1 год за запрос — разбиваем на куски.
    Возвращает DataFrame с колонками (date, close).
    """
    frames = []
    chunk_days = 360       # чуть меньше года — безопасный размер
    cursor = from_

    while cursor < to:
        chunk_end = min(cursor + datetime.timedelta(days=chunk_days), to)
        body = {
            "instrumentId": uid,
            "from": cursor.strftime("%Y-%m-%dT00:00:00Z"),
            "to":   chunk_end.strftime("%Y-%m-%dT23:59:59Z"),
            "interval": "CANDLE_INTERVAL_DAY",
        }
        data = _post(
            "tinkoff.public.invest.api.contract.v1.MarketDataService/GetCandles",
            body,
        )
        candles = data.get("candles", [])
        if candles:
            rows = []
            for c in candles:
                close = _q(c.get("close"))
                t     = c.get("time", "")[:10]   # "2024-01-02T..."→ "2024-01-02"
                if close and t:
                    rows.append({"date": t, "close": close})
            if rows:
                frames.append(pd.DataFrame(rows))

        cursor = chunk_end + datetime.timedelta(days=1)
        time.sleep(_SLEEP)

    if not frames:
        return pd.DataFrame(columns=["date", "close"])

    df = pd.concat(frames, ignore_index=True)
    df["date"]  = pd.to_datetime(df["date"]).dt.normalize()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df.dropna().sort_values("date").drop_duplicates("date")


# ── Инкрементальное обновление CSV ────────────────────────────────────────────

def update_product(isin: str, csv_path: str) -> str:
    """
    Находит инструмент по ISIN, тянет новые свечи (с даты последней записи),
    дополняет CSV. Возвращает строку-статус.
    """
    import pathlib
    path = pathlib.Path(csv_path)

    # Читаем существующий CSV
    if path.exists():
        existing = pd.read_csv(path, parse_dates=["date"])
        existing["date"] = pd.to_datetime(existing["date"]).dt.normalize()
        last_date = existing["date"].max().date()
        from_date = last_date + datetime.timedelta(days=1)
    else:
        existing  = pd.DataFrame(columns=["date", "close"])
        from_date = datetime.date.today() - datetime.timedelta(days=730)

    to_date = datetime.date.today()
    if from_date > to_date:
        return "already_up_to_date"

    # Ищем инструмент
    inst = find_instrument(isin)
    if not inst:
        return f"not_found (ISIN {isin} не найден в T-Bank)"

    logger.info("%s → %s (%s), загружаем с %s", isin, inst["name"], inst["uid"], from_date)

    # Загружаем свечи
    new_df = fetch_candles(inst["uid"], from_date, to_date)
    if new_df.empty:
        return "no_new_candles"

    # Объединяем и сохраняем
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = combined.sort_values("date").drop_duplicates("date")
    combined["date"] = combined["date"].dt.strftime("%Y-%m-%d")
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(path, index=False)

    return f"updated +{len(new_df)} rows → {len(combined)} total | {inst['name']}"
