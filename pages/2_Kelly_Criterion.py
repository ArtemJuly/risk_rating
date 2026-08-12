import plotly.graph_objects as go
import streamlit as st

from site_common import render_header, render_nav

st.set_page_config(
    page_title="Kroko Capital · Критерий Келли",
    page_icon="🐊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

render_header("Управление капиталом")
render_nav("kelly")

st.markdown(
    """
    <style>
    .kc-info {
        background: #FFFFFF;
        border: 1px solid #D9EDDF;
        border-radius: 12px;
        padding: 22px 28px 20px;
        margin-bottom: 24px;
    }
    .kc-info-title { font-size: 11px; font-weight: 700; color: #0C7A56; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
    .kc-info-text  { font-size: 13px; color: #537165; line-height: 1.7; max-width: 780px; }
    .kc-info-text b { color: #1A2B23; }
    .kc-formula {
        font-family: 'JetBrains Mono', monospace;
        background: #F4FAF7; border: 1px solid #D9EDDF; border-radius: 8px;
        padding: 10px 16px; margin: 12px 0; display: inline-block;
        font-size: 14px; color: #0C7A56; font-weight: 600;
    }

    /* Карточки-контейнеры (st.container(border=True)) под фирменный стиль */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div.st-key-kc_params),
    div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div.st-key-kc_results) {
        border: 1px solid #D9EDDF !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 4px rgba(12, 122, 86, 0.06);
    }

    .kc-result-block {
        display: flex; align-items: center; gap: 18px;
        padding: 18px 22px;
        background: #F4FAF7; border: 1px solid #D9EDDF;
        border-radius: 10px; margin-bottom: 16px;
    }
    .kc-result-num { font-size: 40px; font-weight: 800; line-height: 1; flex-shrink: 0; }
    .kc-result-label { font-size: 12px; color: #8AAD99; margin-bottom: 2px; text-transform: uppercase; letter-spacing: 0.5px; }
    .kc-result-sub  { font-size: 13px; color: #537165; margin-top: 2px; }

    .kc-stat {
        background: #FFFFFF; border: 1px solid #D9EDDF; border-radius: 10px;
        padding: 14px 16px; text-align: center;
    }
    .kc-stat-label { font-size: 10px; color: #8AAD99; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
    .kc-stat-value { font-size: 20px; font-weight: 800; color: #1A2B23; }

    .kc-warning {
        background: #FEF3F2; border: 1px solid #FCC9C2; border-radius: 10px;
        padding: 14px 18px; font-size: 13px; color: #B42318; line-height: 1.6;
    }
    .kc-disclaimer {
        background: #EBF5EF; border-radius: 8px; padding: 12px 16px;
        font-size: 12px; color: #537165; line-height: 1.7; margin-top: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Пояснение ────────────────────────────────────────────────────────────────

st.markdown(
    """
    <div class="kc-info">
        <div class="kc-info-title">Что это</div>
        <div class="kc-info-text">
            Критерий Келли — формула расчёта <b>оптимальной доли капитала</b> на одну сделку,
            максимизирующая долгосрочный рост капитала при заданном статистическом преимуществе.
            Слишком маленькая ставка недоиспользует преимущество, слишком большая — ведёт
            к разорению даже при положительном ожидании.
        </div>
        <div class="kc-formula">f* = p − q / b</div>
        <div class="kc-info-text">
            где <b>p</b> — вероятность выигрыша, <b>q = 1 − p</b> — вероятность проигрыша,
            <b>b</b> — отношение среднего выигрыша к среднему убытку.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Ввод параметров ────────────────────────────────────────────────────────────

with st.container(border=True, key="kc_params"):
    st.markdown('<div class="kc-info-title" style="margin-bottom:18px">Параметры сделки</div>',
                unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        win_prob = st.slider("Вероятность выигрыша, %", min_value=1, max_value=99, value=55, step=1)
    with c2:
        avg_win = st.number_input("Средний выигрыш, %", min_value=0.1, value=2.0, step=0.1, format="%.1f")
    with c3:
        avg_loss = st.number_input("Средний убыток, %", min_value=0.1, value=1.0, step=0.1, format="%.1f")

    fraction_label = st.radio(
        "Доля от полного Келли",
        ["Полный Келли (100%)", "Половинный Келли (50%)", "Четверть Келли (25%)"],
        index=1,
        horizontal=True,
        help="Полный критерий Келли даёт теоретически оптимальный рост, но с высокой волатильностью капитала. "
             "На практике трейдеры чаще используют долю от него — это снижает просадки ценой части роста.",
    )
    _fraction_map = {
        "Полный Келли (100%)": 1.0,
        "Половинный Келли (50%)": 0.5,
        "Четверть Келли (25%)": 0.25,
    }
    fraction = _fraction_map[fraction_label]

    capital = st.number_input("Капитал, ₽ (опционально, для примера в деньгах)",
                               min_value=0, value=100_000, step=10_000)

# ── Расчёт ──────────────────────────────────────────────────────────────────

p = win_prob / 100
q = 1 - p
b = avg_win / avg_loss
f_star = p - q / b
edge = p * avg_win - q * avg_loss  # ожидаемый результат на сделку, % от ставки

with st.container(border=True, key="kc_results"):
    if f_star <= 0:
        st.markdown(
            f"""
            <div class="kc-warning">
                ⚠️ <b>Отрицательное математическое ожидание.</b> При вероятности выигрыша {win_prob}%
                и соотношении выигрыш/убыток {b:.2f} критерий Келли рекомендует <b>не открывать сделку</b> —
                в долгосрочной перспективе она уменьшает капитал (ожидаемый результат {edge:+.2f}% на сделку).
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        applied = f_star * fraction
        stake_money = capital * applied
        st.markdown(
            f"""
            <div class="kc-result-block">
                <div class="kc-result-num" style="color:#0C7A56">{applied*100:.1f}%</div>
                <div>
                    <div class="kc-result-label">Рекомендованная доля капитала на сделку</div>
                    <div class="kc-result-sub">{fraction_label}, при капитале {capital:,.0f} ₽ → ≈ {stake_money:,.0f} ₽ на сделку</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        s1, s2, s3 = st.columns(3, gap="medium")
        with s1:
            st.markdown(
                f'<div class="kc-stat"><div class="kc-stat-label">Полный Келли (f*)</div>'
                f'<div class="kc-stat-value">{f_star*100:.1f}%</div></div>',
                unsafe_allow_html=True,
            )
        with s2:
            st.markdown(
                f'<div class="kc-stat"><div class="kc-stat-label">Соотношение выигрыш/убыток (b)</div>'
                f'<div class="kc-stat-value">{b:.2f}</div></div>',
                unsafe_allow_html=True,
            )
        with s3:
            st.markdown(
                f'<div class="kc-stat"><div class="kc-stat-label">Ожидаемый результат / сделку</div>'
                f'<div class="kc-stat-value">{edge:+.2f}%</div></div>',
                unsafe_allow_html=True,
            )

        # ── Визуализация: шкала доли капитала ──────────────────────────────
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=[f_star * 100], y=["Капитал"], orientation="h",
            marker=dict(color="#D9EDDF"), name="Полный Келли", showlegend=True,
            width=0.5,
        ))
        fig.add_trace(go.Bar(
            x=[applied * 100], y=["Капитал"], orientation="h",
            marker=dict(color="#0C7A56"), name=fraction_label, showlegend=True,
            width=0.5,
        ))
        fig.update_layout(
            barmode="overlay",
            height=140,
            margin=dict(l=10, r=10, t=30, b=30),
            paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
            xaxis=dict(title="% капитала на сделку", range=[0, max(f_star * 100 * 1.3, 10)],
                       gridcolor="#EBF5EF", zerolinecolor="#D9EDDF"),
            yaxis=dict(visible=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            font=dict(color="#1A2B23", family="Inter"),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        """
        <div class="kc-disclaimer">
            Расчёт носит справочный характер и не является индивидуальной инвестиционной рекомендацией.
            Критерий Келли чувствителен к точности входных вероятностей — на реальных рынках они
            оцениваются приблизительно, поэтому большинство практиков используют долю
            (½ или ¼) от полного значения f*.
        </div>
        """,
        unsafe_allow_html=True,
    )
