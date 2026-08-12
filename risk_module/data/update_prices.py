"""
update_prices.py — обновление истории цен / NAV из MOEX ISS.

Для каждого продукта в data/products/ скрипт:
  1. Ищет бумагу на MOEX (облигации: TQCB/TQOB/TQOD; фонды: TQTF/TQIF/TQPI).
  2. Если найдена — тянет историю цен с даты последней записи (или за 2 года),
     сохраняет / дополняет data/prices/{ISIN}.csv.
  3. Если не найдена (ОПИФы, зарубежные бумаги) — сообщает и не трогает CSV.

CSV формат (data/prices/{ISIN}.csv):
  date,close
  2024-01-02,97.45
  ...

Запуск:
  python -m risk_module.data.update_prices               # все продукты
  python -m risk_module.data.update_prices --isin RU000A1002S8
  python -m risk_module.data.update_prices --from 2023-01-01
  python -m risk_module.data.update_prices --migrate-xlsx   # разовая миграция xlsx → csv
"""

from __future__ import annotations

import argparse
import datetime
import logging
import pathlib
import sys
import time
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_BASE    = "https://iss.moex.com/iss"
_TIMEOUT = 15
_SLEEP   = 0.35   # задержка между запросами — безопасно для публичного API
_HISTORY_LIMIT = 100  # строк за один запрос (максимум ISS)

# Доски поиска по приоритету: облигации → ETF/БПИФ → ПИФ
_SEARCH_BOARDS = [
    # (board, market, engine, price_column)
    ("TQCB", "bonds",  "stock", "LEGALCLOSEPRICE"),
    ("TQOB", "bonds",  "stock", "LEGALCLOSEPRICE"),
    ("TQOD", "bonds",  "stock", "LEGALCLOSEPRICE"),
    ("TQOE", "bonds",  "stock", "LEGALCLOSEPRICE"),
    ("TQTF", "shares", "stock", "LEGALCLOSEPRICE"),
    ("TQIF", "shares", "stock", "LEGALCLOSEPRICE"),
    ("TQPI", "shares", "stock", "LEGALCLOSEPRICE"),
]

# ── HTTP хелпер ───────────────────────────────────────────────────────────────

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "KrokoCapital-RiskSystem/1.0"


def _get(url: str, params: dict | None = None) -> dict:
    params = {**(params or {}), "iss.meta": "off"}
    for attempt in range(3):
        try:
            r = _SESSION.get(url, params=params, timeout=_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            if attempt == 2:
                raise
            logger.warning("ISS retry %d: %s", attempt + 1, exc)
            time.sleep(1)
    return {}


# ── Поиск активной доски для ISIN ────────────────────────────────────────────

def _find_board(isin: str) -> Optional[tuple[str, str, str, str]]:
    """
    Возвращает (board, market, engine, price_column) или None.
    Сначала смотрим primary board через /securities/{isin},
    потом перебираем _SEARCH_BOARDS.
    """
    # Шаг 1: primary board из /securities
    try:
        data = _get(f"{_BASE}/securities/{isin}.json", {
            "iss.only": "boards",
            "boards.columns": "boardid,market,engine,is_primary",
        })
        rows = data.get("boards", {}).get("data", [])
        primary = [r for r in rows if r[3] == 1]
        if primary:
            bid, mkt, eng, _ = primary[0]
            # Определяем price column по типу рынка
            price_col = "LEGALCLOSEPRICE"
            return bid, mkt, eng, price_col
    except Exception as exc:
        logger.debug("board lookup failed for %s: %s", isin, exc)

    return None


# ── Загрузка истории с одной доски ───────────────────────────────────────────

def _fetch_history(
    isin: str,
    board: str,
    market: str,
    engine: str,
    price_col: str,
    from_date: str,
    till_date: str,
) -> pd.DataFrame:
    """Тянет историю с пагинацией, возвращает DataFrame (date, close)."""
    url = f"{_BASE}/history/engines/{engine}/markets/{market}/boards/{board}/securities/{isin}.json"
    frames = []
    start  = 0

    while True:
        data = _get(url, {
            "from":  from_date,
            "till":  till_date,
            "start": start,
            "history.columns": f"TRADEDATE,{price_col},VOLUME",
        })
        hist  = data.get("history", {})
        rows  = hist.get("data", [])
        cols  = hist.get("columns", [])
        if not rows:
            break

        df = pd.DataFrame(rows, columns=cols)
        df = df.rename(columns={price_col: "close", "TRADEDATE": "date"})
        df = df[["date", "close"]].dropna()
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close"])
        df = df[df["close"] > 0]
        frames.append(df)

        if len(rows) < _HISTORY_LIMIT:
            break
        start += _HISTORY_LIMIT
        time.sleep(_SLEEP)

    if not frames:
        return pd.DataFrame(columns=["date", "close"])
    return pd.concat(frames, ignore_index=True)


# ── CSV helpers ───────────────────────────────────────────────────────────────

def _load_csv(path: pathlib.Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["date", "close"])
    df = pd.read_csv(path, parse_dates=["date"])
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df.sort_values("date").drop_duplicates("date")


def _save_csv(path: pathlib.Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = df.sort_values("date").drop_duplicates("date")
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df.to_csv(path, index=False)


# ── Обновление одного ISIN ────────────────────────────────────────────────────

def update_isin(
    isin: str,
    prices_dir: pathlib.Path,
    from_date: Optional[str] = None,
) -> str:
    """
    Возвращает статус: 'updated N rows', 'already_up_to_date', 'not_on_moex', 'error'.
    """
    csv_path = prices_dir / f"{isin}.csv"
    existing = _load_csv(csv_path)

    # Определяем from_date
    today = datetime.date.today()
    if from_date:
        start = from_date
    elif not existing.empty:
        last = pd.to_datetime(existing["date"].max()).date()
        start = (last + datetime.timedelta(days=1)).isoformat()
    else:
        start = (today - datetime.timedelta(days=730)).isoformat()

    till = today.isoformat()

    if start > till:
        return "already_up_to_date"

    # Ищем доску
    board_info = _find_board(isin)
    if board_info is None:
        return "not_on_moex"

    board, market, engine, price_col = board_info
    logger.info("%s → board %s (%s/%s), from %s", isin, board, market, engine, start)

    try:
        new_df = _fetch_history(isin, board, market, engine, price_col, start, till)
    except Exception as exc:
        return f"error: {exc}"

    if new_df.empty:
        return "not_on_moex"

    new_df["date"] = pd.to_datetime(new_df["date"]).dt.normalize()
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = combined.sort_values("date").drop_duplicates("date")
    _save_csv(csv_path, combined)

    added = len(new_df)
    total = len(combined)
    return f"updated +{added} rows (total {total})"


# ── Миграция xlsx nav → csv ───────────────────────────────────────────────────

def migrate_xlsx(products_dir: pathlib.Path, prices_dir: pathlib.Path) -> None:
    """
    Разовая операция: читает лист 'nav' из каждого products/{ISIN}.xlsx
    и сохраняет его в prices/{ISIN}.csv если CSV ещё не существует или меньше.
    """
    xlsx_files = sorted(products_dir.glob("*.xlsx"))
    if not xlsx_files:
        print("  Нет xlsx файлов в", products_dir)
        return

    for xlsx_path in xlsx_files:
        isin = xlsx_path.stem
        csv_path = prices_dir / f"{isin}.csv"

        try:
            xl  = pd.ExcelFile(xlsx_path)
            if "nav" not in xl.sheet_names:
                print(f"  {isin}: нет листа 'nav', пропускаем")
                continue

            df = xl.parse("nav")
            df.columns = df.columns.astype(str).str.strip()

            if "Date" not in df.columns or "NAV" not in df.columns:
                print(f"  {isin}: нет колонок Date/NAV, пропускаем")
                continue

            nav_raw = (
                df["NAV"].astype(str)
                .str.replace(" ", "", regex=False)
                .str.replace(" ",  "", regex=False)
                .str.replace(",",  ".", regex=False)
            )
            df = pd.DataFrame({
                "date":  pd.to_datetime(df["Date"]).dt.normalize(),
                "close": pd.to_numeric(nav_raw, errors="coerce"),
            }).dropna()

            existing = _load_csv(csv_path)
            if not existing.empty and len(existing) >= len(df):
                print(f"  {isin}: CSV уже актуален ({len(existing)} строк), пропускаем")
                continue

            _save_csv(csv_path, df)
            print(f"  {isin}: мигрировано {len(df)} строк → {csv_path.name}")

        except Exception as exc:
            print(f"  {isin}: ошибка — {exc}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Обновление цен из MOEX ISS")
    parser.add_argument("--isin",          help="Обновить один ISIN")
    parser.add_argument("--from",          dest="from_date", help="Начало периода YYYY-MM-DD")
    parser.add_argument("--migrate-xlsx",  action="store_true",
                        help="Мигрировать NAV из xlsx → csv (разово)")
    args = parser.parse_args()

    # Определяем пути относительно корня проекта
    here        = pathlib.Path(__file__).resolve().parent          # risk_module/data/
    project_dir = here.parent.parent                               # calculator/
    data_dir    = project_dir / "data"
    prices_dir  = data_dir / "prices"
    products_dir = data_dir / "products"

    prices_dir.mkdir(parents=True, exist_ok=True)

    if args.migrate_xlsx:
        print("=== Миграция xlsx → csv ===")
        migrate_xlsx(products_dir, prices_dir)
        print("Готово.\n")

    # Определяем список ISINs
    if args.isin:
        isins = [args.isin.strip().upper()]
    else:
        isins = sorted(p.stem for p in products_dir.glob("*.xlsx"))

    if not isins:
        print("Нет продуктов в", products_dir)
        sys.exit(0)

    print(f"\n=== Обновление цен: {len(isins)} продуктов ===")
    not_on_moex = []

    for isin in isins:
        status = update_isin(isin, prices_dir, from_date=args.from_date)
        icon = "✓" if status.startswith("updated") or "up_to_date" in status else "–"
        print(f"  {icon} {isin}: {status}")
        if status == "not_on_moex":
            not_on_moex.append(isin)
        time.sleep(_SLEEP)

    if not_on_moex:
        print(f"""
━━━ Не найдены на MOEX ({len(not_on_moex)} шт.) ━━━
Для ОПИФов NAV публикуется управляющей компанией и ЦБ РФ.
Чтобы добавить данные вручную, создайте файл:

  data/prices/{{ISIN}}.csv

Формат:
  date,close
  2024-01-02,10208191603.33
  2024-01-03,10225129253.22
  ...

ISINs: {', '.join(not_on_moex)}
""")


if __name__ == "__main__":
    main()
