from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
import pandas as pd
import pathlib
import re
import yaml
from importlib.resources import files  # ✅ для доступа к ресурсам пакета


# --- Нормализация рейтинга ---
_CYR_TO_LAT = {
    "А": "A", "В": "B", "С": "C",  # часто встречается кириллица вместо латиницы
    "а": "A", "в": "B", "с": "C",
}
# Юникодные дефисы/минусы, которые надо сводить к обычному "-"
_DASHES = ["\u2212", "\u2013", "\u2014", "\u2012"]  # −, –, —, ‒

_ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ+-")  # разрешим только буквы A..Z, + и -

def _to_latin(s: str) -> str:
    return "".join(_CYR_TO_LAT.get(ch, ch) for ch in s)

def _fix_dashes(s: str) -> str:
    for d in _DASHES:
        s = s.replace(d, "-")
    return s

def _strip_noise(s: str) -> str:
    """
    Оставляем только A..Z, +, -, в правильном порядке.
    Убираем префиксы/суффиксы типа 'RU', 'RUS', ' (RU)' и прочий мусор.
    """
    s = re.sub(r"\(.*?\)", "", s)        # вырезаем скобки с любым содержимым
    s = re.sub(r"[^A-Z+\-]", "", s)      # удаляем всё, что не A-Z или +/-
    return s

def _norm_rating(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = _to_latin(s)              # кириллицу → латиницу
    s = s.upper()
    s = s.replace(" ", "")
    s = _fix_dashes(s)            # все минусы → "-"
    # частые приставки страны/локали
    s = re.sub(r"^RU[_\-]?", "", s)
    s = re.sub(r"^RUS[_\-]?", "", s)
    s = _strip_noise(s)
    if not s:
        return None
    return s


@dataclass
class RatingBucket:
    skk: int
    avg_def_rate: float  # доля (0..1)
    by_agency: Dict[str, List[str]]

    def match(self, agency: str, rating: str) -> bool:
        return rating in self.by_agency.get(agency, [])


class CreditScale:
    def __init__(self, yaml_path: Optional[str] = None):
        # Берём YAML из ресурсов пакета, если путь не передан явно
        if yaml_path is None:
            yaml_file = files(__package__).joinpath("config/credit_risk_scale.yaml")
        else:
            yaml_file = pathlib.Path(yaml_path)

        with open(yaml_file, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        self.buckets: List[RatingBucket] = []
        for b in raw["buckets"]:
            self.buckets.append(
                RatingBucket(
                    skk=int(b["skk"]),
                    avg_def_rate=float(b["avg_def_rate_pct"]) / 100.0,
                    by_agency={
                        k.lower(): [ _norm_rating(x) for x in v ]
                        for k, v in b["agencies"].items()
                    },
                )
            )

    def lookup(self, agency: str, rating: str) -> Optional[RatingBucket]:
        agency = agency.lower()
        rating = _norm_rating(rating) or ""
        for bucket in self.buckets:
            if bucket.match(agency, rating):
                return bucket
        return None


class CreditRiskByRating:
    """
    Приоритет колонок: CreditExpert → CreditAkra → CreditNKR.
    Возвращает вероятность дефолта в процентах (avg_def_rate_pct) либо None.
    """
    def __init__(
        self,
        db_path: str,
        sheet_name: str = "dataBonds",
        scale_yaml_path: Optional[str] = None,
    ):
        self.db_path = db_path
        self.sheet_name = sheet_name
        self.scale = CreditScale(scale_yaml_path)

    def get_default_probability(self, isin: str) -> Optional[float]:
        df_db = self._load_db()
        df_db["_ISIN"] = df_db["ISIN"].astype(str).str.strip().str.upper()
        isin_norm = str(isin).strip().upper()

        row = df_db.loc[df_db["_ISIN"] == isin_norm]
        if row.empty:
            return None  # ISIN не найден

        r = row.iloc[0]
        rating_expert = _norm_rating(r.get("CreditExpert"))
        rating_akra   = _norm_rating(r.get("CreditAkra"))
        rating_nkr    = _norm_rating(r.get("CreditNKR"))

        if rating_expert:
            agency, rating = "expert", rating_expert
        elif rating_akra:
            agency, rating = "akra", rating_akra
        elif rating_nkr:
            agency, rating = "nkr", rating_nkr
        else:
            return None  # нет ни одного рейтинга

        bucket = self.scale.lookup(agency, rating)
        if bucket is None:
            return None  # не нашли в шкале (например, нестандартный рейтинг)

        return bucket.avg_def_rate * 100.0  # → в процентах

    # Вспомогательный метод для диагностики (можешь удалить после проверки)
    def get_default_probability_debug(self, isin: str) -> Tuple[Optional[float], Dict[str, Any]]:
        df_db = self._load_db()
        df_db["_ISIN"] = df_db["ISIN"].astype(str).str.strip().str.upper()
        isin_norm = str(isin).strip().upper()

        info: Dict[str, Any] = {"isin": isin_norm}

        row = df_db.loc[df_db["_ISIN"] == isin_norm]
        if row.empty:
            info["status"] = "NOT_FOUND_IN_DB"
            return None, info

        r = row.iloc[0]
        raw = {
            "CreditExpert": r.get("CreditExpert"),
            "CreditAkra": r.get("CreditAkra"),
            "CreditNKR": r.get("CreditNKR"),
        }
        normed = {k: _norm_rating(v) for k, v in raw.items()}
        info["raw"] = raw
        info["normed"] = normed

        if normed["CreditExpert"]:
            agency, rating = "expert", normed["CreditExpert"]
            source = "CreditExpert"
        elif normed["CreditAkra"]:
            agency, rating = "akra", normed["CreditAkra"]
            source = "CreditAkra"
        elif normed["CreditNKR"]:
            agency, rating = "nkr", normed["CreditNKR"]
            source = "CreditNKR"
        else:
            info["status"] = "NO_RATING_IN_ROW"
            return None, info

        info["chosen_agency"] = agency
        info["chosen_rating"] = rating
        info["source_column"] = source

        bucket = self.scale.lookup(agency, rating)
        if bucket is None:
            info["status"] = "RATING_NOT_MAPPED"
            return None, info

        info["status"] = "OK"
        info["skk"] = bucket.skk
        info["avg_def_rate"] = bucket.avg_def_rate
        return bucket.avg_def_rate * 100.0, info

    def _load_db(self) -> pd.DataFrame:
        path = pathlib.Path(self.db_path)
        if not path.exists():
            raise FileNotFoundError(f"DB file not found: {self.db_path}")
        df = pd.read_excel(path, sheet_name=self.sheet_name)
        required = {"ISIN", "CreditExpert", "CreditAkra", "CreditNKR"}
        missing = required - set(df.columns.astype(str))
        if missing:
            raise ValueError(f"Missing columns in sheet '{self.sheet_name}': {missing}")
        return df


# ---------------------------------------------------------------------------
# Компонент RiskEngine
# ---------------------------------------------------------------------------

from risk_module.core.models import Portfolio, ComponentResult  # noqa: E402


# Согласованный маппинг СКК (1–6) → рейтинг (1–7).
# 4 пропущен намеренно — резерв для более тонкой градации в будущем.
_SKK_TO_RATING: Dict[int, int] = {1: 1, 2: 2, 3: 3, 4: 5, 5: 6, 6: 7}


class CreditRiskComponent:
    """
    Кредитный риск для портфеля облигаций.

    Логика агрегации:
    1. Для каждого холдинга ищем СКК через CreditRiskByRating.
    2. Считаем взвешенный средний СКК (по весам из Portfolio.holdings).
    3. Округляем до целого → маппим в рейтинг 1–7 через _SKK_TO_RATING.

    Холдинги без рейтинга исключаются из расчёта; их суммарный вес
    фиксируется в meta как uncovered_weight.
    """

    name = "CreditRisk"

    def __init__(
        self,
        db_path: str,
        sheet_name: str = "dataBonds",
        scale_yaml_path: Optional[str] = None,
    ) -> None:
        self._lookup = CreditRiskByRating(db_path, sheet_name, scale_yaml_path)

    def calculate(self, portfolio: Portfolio) -> ComponentResult:
        if not portfolio.holdings:
            return ComponentResult(
                component=self.name,
                rating=1,
                category="qualitative",
                meta={"status": "no_holdings"},
            )

        weighted_skk = 0.0
        covered_weight = 0.0
        found: List[Dict[str, Any]] = []
        not_found: List[Dict[str, Any]] = []

        for holding in portfolio.holdings:
            _, info = self._lookup.get_default_probability_debug(holding.isin)
            if info.get("status") == "OK":
                skk = int(info["skk"])
                weighted_skk += skk * holding.weight
                covered_weight += holding.weight
                found.append({
                    "isin": holding.isin,
                    "weight": holding.weight,
                    "skk": skk,
                    "agency": info.get("chosen_agency"),
                    "rating": info.get("chosen_rating"),
                })
            else:
                not_found.append({
                    "isin": holding.isin,
                    "weight": holding.weight,
                    "status": info.get("status"),
                })

        if covered_weight == 0:
            return ComponentResult(
                component=self.name,
                rating=1,
                category="qualitative",
                meta={
                    "status": "no_ratings_found",
                    "not_found": not_found,
                },
            )

        avg_skk = weighted_skk / covered_weight
        skk_rounded = max(1, min(6, round(avg_skk)))
        rating = _SKK_TO_RATING[skk_rounded]

        return ComponentResult(
            component=self.name,
            rating=rating,
            category="qualitative",
            meta={
                "weighted_avg_skk": round(avg_skk, 2),
                "skk_rounded": skk_rounded,
                "covered_weight": round(covered_weight, 4),
                "uncovered_weight": round(1.0 - covered_weight, 4),
                "holdings": found,
                "not_found": not_found,
            },
        )
