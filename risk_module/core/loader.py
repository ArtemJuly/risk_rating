from __future__ import annotations

import pathlib

import pandas as pd

from .models import Portfolio, Holding


class DataLoader:
    """
    Читает данные продукта из data/products/{isin}.xlsx и собирает Portfolio.

    Ожидаемые листы:
    - "nav"      — обязательный: колонки Date, NAV
    - "holdings" — опциональный: колонки ISIN, Weight
    """

    def __init__(self, data_dir: str | pathlib.Path) -> None:
        self.data_dir = pathlib.Path(data_dir)

    def load(self, isin: str) -> Portfolio:
        path = self.data_dir / "products" / f"{isin}.xlsx"
        if not path.exists():
            raise FileNotFoundError(
                f"Файл продукта не найден: {path}\n"
                f"Ожидается: data/products/{isin}.xlsx"
            )

        xl = pd.ExcelFile(path)

        nav_series = self._load_nav(xl, isin)
        holdings = self._load_holdings(xl) if "holdings" in xl.sheet_names else []

        return Portfolio(
            identifier=isin,
            nav_series=nav_series,
            holdings=holdings,
        )

    def _load_nav(self, xl: pd.ExcelFile, isin: str) -> pd.Series:
        if "nav" not in xl.sheet_names:
            raise ValueError(
                f"Лист 'nav' не найден в файле продукта {isin}. "
                f"Доступные листы: {xl.sheet_names}"
            )
        df = xl.parse("nav")
        df.columns = df.columns.astype(str).str.strip()

        if "Date" not in df.columns or "NAV" not in df.columns:
            raise ValueError(
                f"Лист 'nav' должен содержать колонки Date и NAV. "
                f"Найдено: {list(df.columns)}"
            )

        nav_raw = (
            df["NAV"]
            .astype(str)
            .str.replace(" ", "", regex=False)  # неразрывный пробел
            .str.replace(" ", "", regex=False)        # обычный пробел (разделитель тысяч)
            .str.replace(",", ".", regex=False)        # десятичная запятая → точка
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

    def _load_holdings(self, xl: pd.ExcelFile) -> list[Holding]:
        df = xl.parse("holdings")
        df.columns = df.columns.astype(str).str.strip()

        if "ISIN" not in df.columns or "Weight" not in df.columns:
            raise ValueError(
                f"Лист 'holdings' должен содержать колонки ISIN и Weight. "
                f"Найдено: {list(df.columns)}"
            )

        df = df.dropna(subset=["ISIN", "Weight"])
        return [
            Holding(isin=str(row["ISIN"]).strip(), weight=float(row["Weight"]))
            for _, row in df.iterrows()
        ]
