from __future__ import annotations

from typing import Optional, Protocol

from .models import Portfolio, ComponentResult, RiskResult

# Веса внутри качественного бакета (сумма = 1.0).
# Нормализуются автоматически если часть компонент недоступна.
_QUAL_WEIGHTS: dict[str, float] = {
    "CreditRisk":       0.60,
    "InterestRateRisk": 0.20,
    "LiquidityRisk":    0.10,
    "IssueQuality":     0.10,
}

# Статусы, при которых компонент считается «нет данных» и исключается из расчёта
_NO_DATA = frozenset({"no_holdings", "no_ratings_found", "no_durations_found"})


def _qual_score(results: list[ComponentResult]) -> Optional[float]:
    """Взвешенное среднее качественных компонент (только с данными)."""
    num = 0.0
    den = 0.0
    for r in results:
        if r.category != "qualitative":
            continue
        w = _QUAL_WEIGHTS.get(r.component, 0.0)
        if w == 0.0 or r.meta.get("status") in _NO_DATA:
            continue
        num += r.rating * w
        den += w
    return num / den if den > 0 else None


def _quant_score(results: list[ComponentResult]) -> Optional[int]:
    """Максимум по количественным компонентам."""
    scores = [r.rating for r in results if r.category == "quantitative"]
    return max(scores) if scores else None


class RiskComponent(Protocol):
    """Интерфейс, который должен реализовать каждый компонент риска."""
    name: str

    def calculate(self, portfolio: Portfolio) -> ComponentResult: ...


class RiskEngine:
    """
    Оркестратор: запускает все компоненты и агрегирует результат.

    Формула:
      Q = max(количественные компоненты)          — сигналы из цены
      G = взвешенное среднее качественных          — IRR ≤ 20%, Credit ≥ 60%
      final = max(Q, round((Q + G) / 2))           — Q как пол, значение между Q и G
    Если качественных данных нет — final = Q.
    """

    def __init__(self, components: list[RiskComponent]) -> None:
        if not components:
            raise ValueError("RiskEngine requires at least one component.")
        self.components = components

    def calculate(self, portfolio: Portfolio) -> RiskResult:
        results: list[ComponentResult] = []
        for component in self.components:
            results.append(component.calculate(portfolio))

        Q = _quant_score(results)
        G = _qual_score(results)

        if Q is not None and G is not None:
            blended = (Q + G) / 2.0
            # традиционное округление вместо банковского
            blended_rounded = int(blended + 0.5)
            final_rating = max(Q, blended_rounded)
        elif Q is not None:
            final_rating = Q
        elif G is not None:
            final_rating = max(1, min(7, int(G + 0.5)))
        else:
            final_rating = 1

        final_rating = max(1, min(7, final_rating))

        return RiskResult(
            identifier=portfolio.identifier,
            final_rating=final_rating,
            components=results,
        )
