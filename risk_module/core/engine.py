from __future__ import annotations

from typing import Protocol

from .models import Portfolio, ComponentResult, RiskResult


class RiskComponent(Protocol):
    """Интерфейс, который должен реализовать каждый компонент риска."""
    name: str

    def calculate(self, portfolio: Portfolio) -> ComponentResult: ...


class RiskEngine:
    """
    Оркестратор: запускает все компоненты и агрегирует результат через max().
    Добавление нового компонента — просто передать его в конструктор.
    """

    def __init__(self, components: list[RiskComponent]) -> None:
        if not components:
            raise ValueError("RiskEngine requires at least one component.")
        self.components = components

    def calculate(self, portfolio: Portfolio) -> RiskResult:
        results: list[ComponentResult] = []
        for component in self.components:
            result = component.calculate(portfolio)
            results.append(result)

        final_rating = max(r.rating for r in results)
        return RiskResult(
            identifier=portfolio.identifier,
            final_rating=final_rating,
            components=results,
        )
