from __future__ import annotations

# Верхние границы диапазонов потерь для рейтингов 1–6.
# Рейтинг 7 — всё, что выше 70%.
# Границы включительно: loss_pct <= threshold → рейтинг.
_THRESHOLDS: list[tuple[float, int]] = [
    (0.05, 1),
    (0.10, 2),
    (0.20, 3),
    (0.30, 4),
    (0.50, 5),
    (0.70, 6),
]


class RiskScale:
    """Преобразует ожидаемые максимальные потери (доля, 0.0–1.0) в рейтинг 1–7."""

    @staticmethod
    def loss_to_rating(loss_pct: float) -> int:
        """
        loss_pct — доля потерь, например 0.18 = 18%.
        Значение должно быть неотрицательным.
        """
        loss_pct = abs(loss_pct)
        for threshold, rating in _THRESHOLDS:
            if loss_pct <= threshold:
                return rating
        return 7
