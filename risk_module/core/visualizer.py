from __future__ import annotations

import plotly.graph_objects as go

from .models import RiskResult

# ---------------------------------------------------------------------------
# Палитра
# ---------------------------------------------------------------------------

_BG   = "#0F172A"
_CARD = "#1E293B"
_BORDER = "#334155"
_TEXT = "#F1F5F9"
_MUTED = "#94A3B8"

_RATING_COLOR = {
    1: "#22C55E",
    2: "#84CC16",
    3: "#EAB308",
    4: "#F97316",
    5: "#EF4444",
    6: "#DC2626",
    7: "#991B1B",
}

_LOSS_RANGES = {
    1: "0 – 5%",
    2: "5 – 10%",
    3: "10 – 20%",
    4: "20 – 30%",
    5: "30 – 50%",
    6: "50 – 70%",
    7: "> 70%",
}

_COMPONENT_LABEL = {
    "VaR":              "VaR",
    "StressTest":       "Стресс-тест",
    "CreditRisk":       "Кредитный риск",
    "InterestRateRisk": "Процентный риск",
}


def _color(rating: int) -> str:
    return _RATING_COLOR.get(max(1, min(7, rating)), "#64748B")


# ---------------------------------------------------------------------------
# Примитивы
# ---------------------------------------------------------------------------

def _add_box(
    fig: go.Figure,
    x0: float, y0: float, x1: float, y1: float,
    rating: int,
    label: str,
    sublabel: str = "",
    big: bool = False,
) -> None:
    c = _color(rating)
    fig.add_shape(
        type="rect", x0=x0, y0=y0, x1=x1, y1=y1,
        line=dict(color=c, width=2.5),
        fillcolor=_CARD, layer="below",
    )
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    h  = y1 - y0

    if big:
        fig.add_annotation(x=cx, y=cy + h * 0.14,
                           text=label, font=dict(size=13, color=_MUTED),
                           showarrow=False)
        fig.add_annotation(x=cx, y=cy - h * 0.12,
                           text=str(rating),
                           font=dict(size=52, color=c, family="Arial Black"),
                           showarrow=False)
    else:
        fig.add_annotation(x=x0 + 0.015, y=cy,
                           text=label, xanchor="left",
                           font=dict(size=12, color=_TEXT),
                           showarrow=False)
        fig.add_annotation(x=x1 - 0.015, y=cy,
                           text=str(rating), xanchor="right",
                           font=dict(size=20, color=c, family="Arial Black"),
                           showarrow=False)
        if sublabel:
            fig.add_annotation(x=x0 + 0.015, y=cy - h * 0.28,
                               text=sublabel, xanchor="left",
                               font=dict(size=10, color=_MUTED),
                               showarrow=False)


def _add_line(fig: go.Figure,
              x0: float, y0: float, x1: float, y1: float) -> None:
    fig.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1,
                  line=dict(color=_BORDER, width=1.5, dash="dot"))


def _group_label(fig: go.Figure, x: float, yc: float, text: str) -> None:
    """Вертикальная метка группы слева от блоков."""
    fig.add_annotation(
        x=x, y=yc,
        text=text.upper(),
        textangle=-90,
        font=dict(size=8, color=_MUTED),
        showarrow=False,
        xanchor="center",
    )


# ---------------------------------------------------------------------------
# Основная функция
# ---------------------------------------------------------------------------

def plot_risk_result(result: RiskResult) -> go.Figure:
    """
    Plotly Figure с диаграммой агрегации риск-рейтинга.
    Использование: fig.show() или fig.write_html("output.html")
    """
    quant = [c for c in result.components if c.category == "quantitative"]
    qual  = [c for c in result.components if c.category == "qualitative"]

    quant_rating = max((c.rating for c in quant), default=1)
    qual_rating  = max((c.rating for c in qual),  default=1)

    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor=_BG,
        plot_bgcolor=_BG,
        xaxis=dict(visible=False, range=[0, 1]),
        yaxis=dict(visible=False, range=[0, 1]),
        margin=dict(l=20, r=20, t=60, b=20),
        width=980, height=440,
        title=dict(
            text=(f"<b>Риск-рейтинг</b>"
                  f"  <span style='color:{_MUTED}'>{result.identifier}</span>"),
            font=dict(size=16, color=_TEXT),
            x=0.03, xanchor="left",
        ),
    )
    fig.add_trace(go.Scatter(x=[0], y=[0], mode="markers",
                             marker=dict(opacity=0), showlegend=False))

    # -----------------------------------------------------------------------
    # Геометрия
    # -----------------------------------------------------------------------
    BW, BH = 0.25, 0.13
    GAP    = 0.05
    CW, CH = 0.20, 0.17
    FW, FH = 0.18, 0.32

    x_label  = 0.015          # центр вертикальных меток групп
    x0_comp  = 0.035          # левый край блоков компонент
    x_cat    = 0.42
    x_final  = 0.73

    all_comps = quant + qual
    n         = len(all_comps)
    total_h   = n * BH + (n - 1) * GAP
    y_start   = 0.5 + total_h / 2

    comp_positions: list[float] = []
    for i, comp in enumerate(all_comps):
        yc = y_start - i * (BH + GAP) - BH / 2
        comp_positions.append(yc)
        label = _COMPONENT_LABEL.get(comp.component, comp.component)
        # Исправлено: loss_pct хранится как доля → умножаем на 100 для отображения
        sub = f"потери: {comp.loss_pct * 100:.1f}%" if comp.loss_pct else ""
        _add_box(fig, x0_comp, yc - BH / 2, x0_comp + BW, yc + BH / 2,
                 comp.rating, label, sub)

    # Разделитель quant / qual
    n_q = len(quant)
    if 0 < n_q < n:
        sep_y = (comp_positions[n_q - 1] - BH / 2
                 + comp_positions[n_q] + BH / 2) / 2
        fig.add_shape(type="line",
                      x0=x0_comp, y0=sep_y, x1=x0_comp + BW, y1=sep_y,
                      line=dict(color=_BORDER, width=1, dash="dash"))

    # Вертикальные метки групп — левее блоков, не перекрывают их
    ys_quant = comp_positions[:n_q]
    ys_qual  = comp_positions[n_q:]
    if ys_quant:
        _group_label(fig, x_label,
                     (max(ys_quant) + min(ys_quant)) / 2,
                     "Количественные")
    if ys_qual:
        _group_label(fig, x_label,
                     (max(ys_qual) + min(ys_qual)) / 2,
                     "Качественные")

    # -----------------------------------------------------------------------
    # Категориальные блоки
    # -----------------------------------------------------------------------
    yc_quant = sum(ys_quant) / len(ys_quant) if ys_quant else 0.7
    yc_qual  = sum(ys_qual)  / len(ys_qual)  if ys_qual  else 0.3

    if quant:
        _add_box(fig,
                 x_cat - CW / 2, yc_quant - CH / 2,
                 x_cat + CW / 2, yc_quant + CH / 2,
                 quant_rating, "Количественный")
    if qual:
        _add_box(fig,
                 x_cat - CW / 2, yc_qual - CH / 2,
                 x_cat + CW / 2, yc_qual + CH / 2,
                 qual_rating, "Качественный")

    # -----------------------------------------------------------------------
    # Итоговый блок
    # -----------------------------------------------------------------------
    yc_final = 0.5
    _add_box(fig,
             x_final - FW / 2, yc_final - FH / 2,
             x_final + FW / 2, yc_final + FH / 2,
             result.final_rating, "Итоговый рейтинг", big=True)

    # -----------------------------------------------------------------------
    # Соединительные линии
    # -----------------------------------------------------------------------
    x_comp_right = x0_comp + BW
    x_cat_left   = x_cat - CW / 2
    x_cat_right  = x_cat + CW / 2
    x_final_left = x_final - FW / 2

    for yc in ys_quant:
        _add_line(fig, x_comp_right, yc, x_cat_left, yc_quant)
    for yc in ys_qual:
        _add_line(fig, x_comp_right, yc, x_cat_left, yc_qual)
    if quant:
        _add_line(fig, x_cat_right, yc_quant, x_final_left, yc_final)
    if qual:
        _add_line(fig, x_cat_right, yc_qual,  x_final_left, yc_final)

    # -----------------------------------------------------------------------
    # Шкала: два столбца — рейтинг + диапазон потерь
    # -----------------------------------------------------------------------
    lx_box  = 0.885     # центр цветного блока с номером
    lw_box  = 0.038
    lh      = 0.074
    ly0     = 0.875
    ly_step = lh + 0.012

    # Заголовки столбцов
    fig.add_annotation(x=lx_box, y=ly0 + 0.052,
                       text="РР", font=dict(size=8, color=_MUTED),
                       showarrow=False)
    fig.add_annotation(x=lx_box + 0.072, y=ly0 + 0.052,
                       text="ПОТЕРИ", font=dict(size=8, color=_MUTED),
                       showarrow=False, xanchor="center")

    for r in range(1, 8):
        yc = ly0 - (r - 1) * ly_step
        c  = _color(r)

        # Цветной блок с номером
        fig.add_shape(type="rect",
                      x0=lx_box - lw_box / 2, y0=yc - lh / 2,
                      x1=lx_box + lw_box / 2, y1=yc + lh / 2,
                      fillcolor=c, line=dict(color=c))
        fig.add_annotation(x=lx_box, y=yc, text=str(r),
                           font=dict(size=11, color=_BG, family="Arial Black"),
                           showarrow=False)

        # Диапазон потерь
        fig.add_annotation(x=lx_box + 0.072, y=yc,
                           text=_LOSS_RANGES[r],
                           xanchor="center",
                           font=dict(size=10, color=_TEXT),
                           showarrow=False)

    return fig
