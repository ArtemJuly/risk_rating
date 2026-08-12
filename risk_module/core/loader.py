from __future__ import annotations

import pathlib

import pandas as pd

from .models import Portfolio, Holding


class DataLoader:
    """
    Читает данные продукта и собирает Portfolio.

    Источники цен (приоритет по убыванию):
      1. data/prices/{ISIN}.csv  — автообновление через update_prices.py
      2. data/products/{ISIN}.xlsx лист "nav" — ручной / исторический

    Холдинги всегда из data/products/{ISIN}.xlsx лист "holdings".
    """

    def __init__(self, data_dir: str | pathlib.Path) -> None:
        self.data_dir = pathlib.Path(data_dir)

    def load(self, isin: str) -> Portfolio:
        product_path = self.data_dir / "products" / f"{isin}.xlsx"
        csv_path     = self.data_dir / "prices"   / f"{isin}.csv"

        if not product_path.exists() and not csv_path.exists():
            raise FileNotFoundError(
                f"Продукт не найден: нет ни {csv_path.name} ни {product_path.name}"
            )

        nav_series = (
            self._load_nav_csv(csv_path, isin)
            if csv_path.exists()
            else self._load_nav_xlsx(product_path, isin)
        )

        holdings: list[Holding] = []
        if product_path.exists():
            xl = pd.ExcelFile(product_path)
            if "holdings" in xl.sheet_names:
                holdings = self._load_holdings(xl)

        return Portfolio(identifier=isin, nav_series=nav_series, holdings=holdings)

    # ── CSV (приоритетный источник) ───────────────────────────────────────────

    def _load_nav_csv(self, path: pathlib.Path, isin: str) -> pd.Series:
        df = pd.read_csv(path, parse_dates=["date"])
        df = df.dropna(subset=["date", "close"])
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close"])
        series = (
            df.set_index(pd.to_datetime(df["date"]).dt.normalize())["close"]
            .sort_index()
            .drop_duplicates()
        )
        series.name = isin
        return series

    # ── xlsx (fallback) ───────────────────────────────────────────────────────

    def _load_nav_xlsx(self, path: pathlib.Path, isin: str) -> pd.Series:
        if not path.exists():
            raise FileNotFoundError(f"Файл продукта не найден: {path}")
        xl = pd.ExcelFile(path)
        if "nav" not in xl.sheet_names:
            raise ValueError(f"Нет листа 'nav' в {path.name}. Листы: {xl.sheet_names}")
        df = xl.parse("nav")
        df.columns = df.columns.astype(str).str.strip()
        if "Date" not in df.columns or "NAV" not in df.columns:
            raise ValueError(f"Нужны колонки Date и NAV. Найдено: {list(df.columns)}")

        nav_raw = (
            df["NAV"].astype(str)
            .str.replace(" ", "", regex=False)
            .str.replace(" ",      "", regex=False)
            .str.replace(",",      ".", regex=False)
        )
        df = df.copy()
        df["NAV"] = pd.to_numeric(nav_raw, errors="coerce")
        series = (
            df.set_index(pd.to_datetime(df["Date"]))["NAV"]
            .sort_index()
            .dropna()
        )
        series.index = series.index.normalize()
        series.name = isin
        return series

    # ── Holdings ──────────────────────────────────────────────────────────────

    def _load_holdings(self, xl: pd.ExcelFile) -> list[Holding]:
        df = xl.parse("holdings")
        df.columns = df.columns.astype(str).str.strip()
        if "ISIN" not in df.columns or "Weight" not in df.columns:
            raise ValueError(f"Нужны колонки ISIN и Weight. Найдено: {list(df.columns)}")
        df = df.dropna(subset=["ISIN", "Weight"])
        return [
            Holding(isin=str(row["ISIN"]).strip(), weight=float(row["Weight"]))
            for _, row in df.iterrows()
        ]
