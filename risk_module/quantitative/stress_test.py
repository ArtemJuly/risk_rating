from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

import pandas as pd

from risk_module.core.models import Portfolio, ComponentResult
from risk_module.core.scale import RiskScale


# ---------------------------------------------------------------------------
# Утилита: загрузка ценового ряда из Excel
# ---------------------------------------------------------------------------

def _load_price_series(filepath: str, column_name: str) -> pd.Series:
    """
    Читает Excel с ценами:
    - первая колонка — даты (индекс)
    - первая числовая колонка — цены
    Нормализует даты по полуночи, чистит пробелы и запятые.
    """
    df = pd.read_excel(filepath)
    df.columns = df.columns.astype(str)
    df[df.columns[0]] = pd.to_datetime(df[df.columns[0]])
    df.set_index(df.columns[0], inplace=True)
    df.index = df.index.normalize()

    raw = df.iloc[:, 0].astype(str).str.replace(" ", "").str.replace(",", ".")
    series = pd.to_numeric(raw, errors="coerce")
    series.name = column_name
    return series


# ---------------------------------------------------------------------------
# Простой стресс-тест (утилита, не компонент)
# ---------------------------------------------------------------------------

@dataclass
class StressScenario:
    name: str
    shock_factor: float  # 0.2 = -20%
    meta: Dict[str, Any] | None = None


class StressTest:
    """Простой стресс-тест с пропорциональным шоком ко всей стоимости."""

    @staticmethod
    def apply_portfolio_shock(portfolio_value: float, shock_factor: float) -> float:
        return max(portfolio_value * (1 - shock_factor), 0.0)

    @staticmethod
    def run_scenario(portfolio_value: float, scenario: StressScenario) -> Dict[str, Any]:
        stressed = StressTest.apply_portfolio_shock(portfolio_value, scenario.shock_factor)
        return {
            "scenario": scenario.name,
            "shock_factor": scenario.shock_factor,
            "initial_value": portfolio_value,
            "stressed_value": stressed,
            "pnl": stressed - portfolio_value,
            "meta": scenario.meta or {},
        }


# ---------------------------------------------------------------------------
# Модельный стресс-тест — компонент RiskEngine
# ---------------------------------------------------------------------------

try:
    from lightautoml.automl.presets.tabular_presets import TabularAutoML
    from lightautoml.tasks import Task
    from sklearn.metrics import mean_absolute_percentage_error
    _LAMA_AVAILABLE = True
except Exception:
    _LAMA_AVAILABLE = False


class StressTestLAMAComponent:
    """
    Модельный стресс-тест на базе LightAutoML.

    Логика:
    1. Обучает AutoML предсказывать дневные доходности фонда
       по доходностям IMOEX и RGBITR на тренировочном периоде
       (всё, что раньше stress_start).
    2. Прогнозирует доходности фонда на стресс-периоде
       [stress_start, stress_end].
    3. Считает накопленную доходность → loss_pct → рейтинг 1–7.

    Рыночные данные (IMOEX, RGBITR) — один длинный ряд;
    граница train/stress задаётся датами, не разными файлами.
    """

    name = "StressTest"

    def __init__(
        self,
        moex_file: str,
        rgbitr_file: str,
        stress_start: str,
        stress_end: str,
        timeout: int = 300,
    ) -> None:
        if not _LAMA_AVAILABLE:
            raise ImportError(
                "lightautoml / scikit-learn не установлены. "
                "pip install lightautoml scikit-learn"
            )
        self.moex_file = moex_file
        self.rgbitr_file = rgbitr_file
        self.stress_start = pd.Timestamp(stress_start).normalize()
        self.stress_end = pd.Timestamp(stress_end).normalize()
        self.timeout = timeout

    def calculate(self, portfolio: Portfolio) -> ComponentResult:
        # --- Загрузка рыночных данных ---
        moex = _load_price_series(self.moex_file, "IMOEX")
        rgbitr = _load_price_series(self.rgbitr_file, "RGBITR")

        # --- NAV фонда из Portfolio ---
        fund = portfolio.nav_series.copy()
        fund.index = pd.DatetimeIndex(fund.index).normalize()
        fund.name = "Fund"

        # --- Train: пересечение периода фонда с рыночными данными ---
        # Фонд не обязан существовать в стресс-периоде — модель обучается
        # на всей доступной истории фонда и применяется к историческому стрессу.
        train = (
            pd.concat([fund, moex, rgbitr], axis=1)
            .dropna()
            .pct_change()
            .dropna()
        )

        # --- Stress features: только рынок за стресс-период ---
        stress_features = (
            pd.concat([moex, rgbitr], axis=1)
            .loc[self.stress_start:self.stress_end]
            .dropna()
            .pct_change()
            .dropna()
        )

        if train.empty:
            raise ValueError(
                f"[StressTest] Нет тренировочных данных: нет пересечения между "
                f"nav_series ({portfolio.identifier}) и рыночными файлами."
            )
        if stress_features.empty:
            raise ValueError(
                f"[StressTest] Нет рыночных данных в стресс-периоде "
                f"{self.stress_start.date()} – {self.stress_end.date()}."
            )

        # --- Обучение AutoML ---
        task = Task("reg")
        roles = {"target": "Fund"}
        automl = TabularAutoML(
            task=task,
            timeout=self.timeout,
            cpu_limit=2,
            reader_params={"n_jobs": 1},
        )
        oof_pred = automl.fit_predict(train, roles=roles)
        mape = float(mean_absolute_percentage_error(train["Fund"], oof_pred.data))

        # --- Прогноз на стресс-периоде ---
        pred = automl.predict(stress_features)
        stress_returns = pd.Series(
            pred.data.ravel(),
            index=stress_features.index,
            name="Fund_pred",
        )

        # --- Метрики ---
        cum_return = float((1 + stress_returns).prod() - 1)
        cum_prod = (1 + stress_returns).cumprod()
        max_drawdown = float((cum_prod / cum_prod.cummax() - 1).min())

        # Потери — только если накопленная доходность отрицательная
        loss_pct = abs(min(0.0, cum_return))
        rating = RiskScale.loss_to_rating(loss_pct)

        return ComponentResult(
            component=self.name,
            rating=rating,
            category="quantitative",
            loss_pct=loss_pct,
            meta={
                "stress_start": str(self.stress_start.date()),
                "stress_end": str(self.stress_end.date()),
                "cumulative_return": round(cum_return, 6),
                "max_drawdown": round(max_drawdown, 6),
                "mape_train": round(mape, 6),
                "n_train": len(train),
                "n_stress": len(stress_returns),
            },
        )
