# risk_module/quantitative/stress_test.py

from dataclasses import dataclass
from typing import Dict, Any, Iterable, List

import pandas as pd
import numpy as np

# --- Базовый простой стресс-тест (оставляем, если пригодится) ---

@dataclass
class StressScenario:
    name: str
    shock_factor: float  # 0.2 = -20%
    meta: Dict[str, Any] | None = None

class StressTest:
    """Простой стресс-тест с пропорциональным шоком ко всей стоимости."""
    @staticmethod
    def apply_portfolio_shock(portfolio_value: float, shock_factor: float) -> float:
        stressed_value = portfolio_value * (1 - shock_factor)
        return max(stressed_value, 0.0)

    @staticmethod
    def run_scenario(portfolio_value: float, scenario: StressScenario) -> Dict[str, Any]:
        stressed = StressTest.apply_portfolio_shock(portfolio_value, scenario.shock_factor)
        pnl = stressed - portfolio_value
        return {
            "scenario": scenario.name,
            "shock_factor": scenario.shock_factor,
            "initial_value": portfolio_value,
            "stressed_value": stressed,
            "pnl": pnl,
            "meta": scenario.meta or {},
        }

# --- Твой LAMA-стресс-тест (модель + прогноз на стресс-период) ---

try:
    # Импорты внутри try: если LAMA не установлена, импорт модуля не «падает».
    from lightautoml.automl.presets.tabular_presets import TabularAutoML
    from lightautoml.tasks import Task
    from sklearn.metrics import mean_absolute_percentage_error
    _LAMA_AVAILABLE = True
except Exception:
    _LAMA_AVAILABLE = False

class StressTestLAMA:
    """
    Модельный стресс-тест:
    - обучает AutoML прогнозировать доходность фонда по индексам IMOEX/RGBITR на train-периоде
    - применяет модель на stress-периоде (файлы для IMOEX/RGBITR)
    - отдает прогноз ряда доходностей фонда и сводные метрики
    """

    def __init__(
        self,
        fund_file: str,
        moex_file: str,
        rgbitr_file: str,
        moex_stress_file: str,
        rgbitr_stress_file: str,
    ):
        if not _LAMA_AVAILABLE:
            raise ImportError(
                "lightautoml / scikit-learn не установлены. "
                "Установи зависимости: pip install lightautoml scikit-learn"
            )
        self.fund_file = fund_file
        self.moex_file = moex_file
        self.rgbitr_file = rgbitr_file
        self.moex_stress_file = moex_stress_file
        self.rgbitr_stress_file = rgbitr_stress_file

        self.model = None
        self.mape_score = None
        self.train_data = None
        self.stress_result = None

    @staticmethod
    def preprocess_price_file(filepath: str, column_name: str) -> pd.Series:
        """
        Читает Excel с ценами:
        - первая колонка — даты (становится индексом)
        - первая числовая колонка — значения цен (поле column_name)
        - нормализует дату по полуночи, чистит пробелы и запятые
        """
        df = pd.read_excel(filepath)
        df.columns = df.columns.astype(str)
        df[df.columns[0]] = pd.to_datetime(df[df.columns[0]])
        df.set_index(df.columns[0], inplace=True)
        df.index = df.index.normalize()

        raw_series = df.iloc[:, 0].astype(str).str.replace(" ", "").str.replace(",", ".")
        series = pd.to_numeric(raw_series, errors="coerce")
        series.name = column_name
        return series

    def _load_and_prepare(self):
        """Готовит train-датасет: Fund, IMOEX, RGBITR → дневные доходности."""
        fund = self.preprocess_price_file(self.fund_file, "Fund")
        moex = self.preprocess_price_file(self.moex_file, "IMOEX")
        rgbitr = self.preprocess_price_file(self.rgbitr_file, "RGBITR")
        df = pd.concat([fund, moex, rgbitr], axis=1).dropna()
        self.train_data = df.pct_change().dropna()

    def _load_stress_data(self):
        """Готовит stress-признаки: IMOEX, RGBITR → доходности."""
        moex = self.preprocess_price_file(self.moex_stress_file, "IMOEX")
        rgbitr = self.preprocess_price_file(self.rgbitr_stress_file, "RGBITR")
        df = pd.concat([moex, rgbitr], axis=1).dropna()
        return df.pct_change().dropna()

    def train_model(self, timeout: int = 300):
        """Обучает TabularAutoML предсказывать доходность фонда (target='Fund')."""
        from lightautoml.tasks import Task
        from lightautoml.automl.presets.tabular_presets import TabularAutoML
        from sklearn.metrics import mean_absolute_percentage_error

        self._load_and_prepare()
        task = Task("reg")
        roles = {"target": "Fund"}
        automl = TabularAutoML(task=task, timeout=timeout, cpu_limit=2, reader_params={"n_jobs": 1})
        oof_pred = automl.fit_predict(self.train_data, roles=roles)

        self.model = automl
        self.mape_score = mean_absolute_percentage_error(self.train_data["Fund"], oof_pred.data)
        return self.mape_score

    def predict_stress(self) -> pd.Series:
        """Стресс-прогноз доходностей фонда на основе стресс-признаков."""
        if self.model is None:
            raise RuntimeError("Model is not trained. Call train_model() first.")
        stress_data = self._load_stress_data()
        pred = self.model.predict(stress_data)
        self.stress_result = pd.Series(pred.data.ravel(), index=stress_data.index, name="Fund_pred")
        return self.stress_result

    def get_summary(self) -> Dict[str, Any]:
        """Агрегированные метрики по стресс-прогнозу."""
        if self.stress_result is None:
            raise RuntimeError("No stress predictions. Call predict_stress() first.")
        cum_return = (1 + self.stress_result).prod() - 1
        rolling_max = (1 + self.stress_result).cumprod().cummax()
        drawdown = (1 + self.stress_result).cumprod() / rolling_max - 1
        max_drawdown = float(drawdown.min())
        return {
            "MAPE (train)": float(self.mape_score) if self.mape_score is not None else None,
            "Cumulative return (stress)": float(cum_return),
            "Max drawdown (stress)": max_drawdown,
        }
