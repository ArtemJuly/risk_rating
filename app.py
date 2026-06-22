import pathlib
import pandas as pd
import streamlit as st

BASE_DIR = pathlib.Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

st.set_page_config(
    page_title="Kroko Capital · Risk Rating",
    page_icon="🐊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 !important; max-width: 100% !important; }
section[data-testid="stSidebar"] { display: none; }

/* ── Шапка ──────────────────────────────────────────────────────── */
.rr-header {
    background: linear-gradient(135deg, #050C18 0%, #0B1A30 70%, #0F2040 100%);
    border-bottom: 1px solid #1B3158;
    padding: 18px 40px;
    display: flex; align-items: center; justify-content: space-between;
}
.rr-brand { display: flex; align-items: center; gap: 14px; }
.rr-logo {
    width: 42px; height: 42px;
    background: linear-gradient(135deg, #1D4ED8, #3B82F6);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; line-height: 1;
}
.rr-brand-name  { font-size: 22px; font-weight: 800; color: #E2EAF4; letter-spacing: -0.5px; }
.rr-brand-sub   { font-size: 11px; color: #4A6B8A; text-transform: uppercase; letter-spacing: 1px; margin-top: 2px; }
.rr-header-pill {
    background: #0D1B2E; border: 1px solid #1B3A6B;
    border-radius: 20px; padding: 5px 16px;
    font-size: 12px; color: #5A9BDB; font-weight: 500;
}

/* ── Основной контейнер ─────────────────────────────────────────── */
.rr-body { padding: 28px 40px 60px; }

/* ── Информационная панель ──────────────────────────────────────── */
.rr-info {
    background: #0D1B2E;
    border: 1px solid #1B3158;
    border-radius: 12px;
    padding: 24px 28px;
    margin-bottom: 28px;
}
.rr-info-title {
    font-size: 13px; font-weight: 700; color: #E2EAF4;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;
}
.rr-info-text {
    font-size: 13px; color: #7A9ABE; line-height: 1.7;
    max-width: 780px; margin-bottom: 20px;
}
.rr-info-text b { color: #C8D8EE; }

/* Шкала рейтинга */
.rr-scale { display: flex; gap: 8px; margin-top: 4px; }
.rr-scale-item {
    flex: 1;
    background: #0B1520;
    border-radius: 8px;
    padding: 10px 8px 10px;
    text-align: center;
    border-top: 3px solid transparent;
}
.rr-scale-num  { font-size: 20px; font-weight: 800; line-height: 1; margin-bottom: 5px; }
.rr-scale-name { font-size: 10px; color: #4A6B8A; line-height: 1.3; }
.rr-scale-loss { font-size: 10px; color: #334D68; margin-top: 4px; font-family: 'JetBrains Mono', monospace; }

/* ── Стат-карточки ──────────────────────────────────────────────── */
.rr-stats { display: flex; gap: 12px; margin-bottom: 24px; }
.rr-stat {
    background: #0D1B2E; border: 1px solid #1B3158;
    border-radius: 10px; padding: 16px 20px; flex: 1;
}
.rr-stat-label { font-size: 11px; color: #4A6B8A; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 6px; }
.rr-stat-value { font-size: 26px; font-weight: 700; color: #E2EAF4; line-height: 1; }
.rr-stat-sub   { font-size: 11px; color: #3B6EA8; margin-top: 4px; }

/* ── Поиск ──────────────────────────────────────────────────────── */
.rr-search-wrap { margin-bottom: 12px; }
.rr-search-wrap input {
    background: #0D1B2E !important;
    border: 1px solid #1B3158 !important;
    border-radius: 8px !important;
    color: #E2EAF4 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 14px !important;
    padding: 10px 16px !important;
}
.rr-search-wrap input:focus { border-color: #3B82F6 !important; }
div[data-testid="stTextInput"] label { display: none !important; }
div[data-testid="stTextInput"] > div { margin-top: 0 !important; }

/* ── Таблица ────────────────────────────────────────────────────── */
.rr-th {
    display: grid;
    grid-template-columns: 2.5fr 2fr 0.7fr 0.7fr 0.7fr 0.7fr 56px;
    gap: 8px; padding: 0 20px 10px;
    border-bottom: 1px solid #1B3158; margin-bottom: 8px;
}
.rr-th-main { font-size: 12px; font-weight: 600; color: #7A9ABE; text-transform: uppercase; letter-spacing: 0.8px; }
.rr-th-info { font-size: 11px; font-weight: 500; color: #2D4A66; text-transform: uppercase; letter-spacing: 0.8px; }
.rr-th-info::before { content: "ℹ "; }

.rr-row {
    display: grid;
    grid-template-columns: 2.5fr 2fr 0.7fr 0.7fr 0.7fr 0.7fr 56px;
    gap: 8px; align-items: center;
    background: #0D1B2E;
    border: 1px solid #1B3158;
    border-left: 3px solid transparent;
    border-radius: 8px;
    padding: 14px 20px; margin-bottom: 6px;
    transition: background 0.12s, border-left-color 0.12s;
}
.rr-row:hover { background: #102035; }

/* ISIN — крупно, моноширинно */
.rr-isin {
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px; font-weight: 600; color: #C8D8EE;
}

/* Рейтинг в строке — крупно */
.rr-rating-cell { display: flex; align-items: center; gap: 10px; }
.rr-rating-label { font-size: 13px; font-weight: 600; }

/* Вспомогательные компоненты — мелко */
.rr-badge {
    display: inline-flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; border-radius: 5px;
    font-size: 13px; font-weight: 800; color: #070E1C;
}
.rr-badge-lg {
    display: inline-flex; align-items: center; justify-content: center;
    width: 48px; height: 48px; border-radius: 10px;
    font-size: 24px; font-weight: 800; color: #070E1C;
}

/* ── Кнопки ─────────────────────────────────────────────────────── */
.stButton > button {
    background: #0F2040 !important; border: 1px solid #1B3A6B !important;
    border-radius: 6px !important; color: #5A9BDB !important;
    font-size: 14px !important; font-weight: 600 !important;
    padding: 4px 14px !important; transition: all 0.12s !important;
}
.stButton > button:hover { background: #1D4ED8 !important; border-color: #3B82F6 !important; color: #fff !important; }

/* ── Детали: шапка ─────────────────────────────────────────────── */
.rr-detail-header {
    background: linear-gradient(135deg, #0D1B2E, #0F2040);
    border: 1px solid #1B3158; border-radius: 12px;
    padding: 28px 32px; margin-bottom: 24px;
    display: flex; align-items: center; justify-content: space-between;
}
.rr-detail-isin  { font-family: 'JetBrains Mono', monospace; font-size: 30px; font-weight: 700; color: #E2EAF4; }
.rr-detail-meta  { font-size: 13px; color: #4A6B8A; margin-top: 6px; }
.rr-detail-right { text-align: right; }
.rr-detail-rlabel { font-size: 11px; color: #4A6B8A; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px; }
.rr-detail-rname { font-size: 13px; font-weight: 600; margin-top: 8px; }

/* ── Детали: сетка компонент ────────────────────────────────────── */
.rr-comp-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 20px 0; }
.rr-comp-card {
    background: #0D1B2E; border-radius: 10px;
    padding: 20px 16px; text-align: center;
    position: relative; overflow: hidden;
}
.rr-comp-label { font-size: 11px; color: #4A6B8A; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 10px; }
.rr-comp-num   { font-size: 52px; font-weight: 800; line-height: 1; margin-bottom: 6px; }
.rr-comp-sub   { font-size: 11px; color: #4A6B8A; }

/* ── Секция-заголовок ───────────────────────────────────────────── */
.rr-section {
    font-size: 12px; font-weight: 600; color: #4A6B8A;
    text-transform: uppercase; letter-spacing: 1px;
    padding-bottom: 10px; border-bottom: 1px solid #1B3158; margin-bottom: 16px;
}
.stDataFrame { border: 1px solid #1B3158 !important; border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

# ── Справочники ───────────────────────────────────────────────────────────────

_CLR = {1:"#22C55E", 2:"#84CC16", 3:"#EAB308", 4:"#F97316", 5:"#EF4444", 6:"#DC2626", 7:"#7F1D1D"}
_RISK_LABEL = {
    1:"Минимальный", 2:"Низкий", 3:"Умеренно низкий",
    4:"Умеренный",   5:"Умеренно высокий", 6:"Высокий", 7:"Максимальный",
}
_LOSS_RANGE = {1:"0–5%", 2:"5–10%", 3:"10–20%", 4:"20–30%", 5:"30–50%", 6:"50–70%", 7:">70%"}
_COMP_LABEL = {
    "VaR":"VaR", "StressTest":"Стресс-тест",
    "CreditRisk":"Кредитный риск", "InterestRateRisk":"Процентный риск",
    "LiquidityRisk":"Ликвидность", "IssueQuality":"Качество эмитентов",
}

def _badge(r, large=False) -> str:
    c = _CLR.get(r, "#334155")
    cls = "rr-badge-lg" if large else "rr-badge"
    return f'<span class="{cls}" style="background:{c}">{r}</span>'

# ── Engine ────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _get_engine():
    from risk_module.quantitative.var import VaRComponent
    from risk_module.quantitative.beta_stress import BetaStressComponent
    from risk_module.qualitative.credit_risk.by_rating import CreditRiskComponent
    from risk_module.qualitative.interest_rate_risk.by_duration import InterestRateRiskComponent
    from risk_module.core.engine import RiskEngine
    db = str(DATA_DIR / "reference" / "bonds_db.xlsx")
    return RiskEngine([
        VaRComponent(),
        BetaStressComponent(
            index_file=str(DATA_DIR / "market" / "rgbitr.xlsx"),
            stress_start="2014-07-01", stress_end="2014-12-31", index_label="RGBITR",
        ),
        CreditRiskComponent(db_path=db),
        InterestRateRiskComponent(db_path=db),
    ])

@st.cache_data(show_spinner=False)
def _compute(isin: str):
    from risk_module.core.loader import DataLoader
    loader = DataLoader(DATA_DIR)
    portfolio = loader.load(isin)
    result = _get_engine().calculate(portfolio)
    return result, portfolio

def _available_isins():
    return sorted(p.stem for p in (DATA_DIR / "products").glob("*.xlsx"))

# ── Session state ─────────────────────────────────────────────────────────────

if "selected" not in st.session_state:
    st.session_state.selected = None

# ── Шапка ────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="rr-header">
  <div class="rr-brand">
    <div class="rr-logo">🐊</div>
    <div>
      <div class="rr-brand-name">Kroko Capital</div>
      <div class="rr-brand-sub">Risk Rating System</div>
    </div>
  </div>
  <div class="rr-header-pill">Аналитика рисков · Внутренняя платформа</div>
</div>
<div class="rr-body">
""", unsafe_allow_html=True)

# ── Информационная панель ─────────────────────────────────────────────────────

def _info_panel():
    scale_items = "".join(f"""
    <div class="rr-scale-item" style="border-top-color:{_CLR[r]}">
        <div class="rr-scale-num" style="color:{_CLR[r]}">{r}</div>
        <div class="rr-scale-name">{_RISK_LABEL[r]}</div>
        <div class="rr-scale-loss">{_LOSS_RANGE[r]}</div>
    </div>""" for r in range(1, 8))

    st.markdown(f"""
    <div class="rr-info">
        <div class="rr-info-title">Что такое риск-рейтинг?</div>
        <div class="rr-info-text">
            Риск-рейтинг — это интегральная оценка уровня риска инвестиционного продукта
            по шкале от <b>1 (минимальный)</b> до <b>7 (максимальный)</b>.<br>
            Рассчитывается на основе <b>количественных</b> метрик (исторический VaR, бета-стресс-тест)
            и <b>качественных</b> (кредитный риск эмитентов, процентный риск дюрации).
            Итоговый рейтинг равен <b>максимуму</b> среди всех компонент — ориентируйтесь именно на него.
            Компоненты VaR, Стресс, Кредит, Ставка даны <b>справочно</b>: они помогают понять,
            что именно является источником риска.
        </div>
        <div class="rr-scale">{scale_items}</div>
    </div>
    """, unsafe_allow_html=True)

# ── Список ────────────────────────────────────────────────────────────────────

def show_list():
    isins = _available_isins()
    if not isins:
        st.warning("Нет файлов в data/products/")
        return

    _info_panel()

    # Считаем рейтинги
    results = {}
    for isin in isins:
        try:
            results[isin], _ = _compute(isin)
        except Exception:
            pass

    ratings = [r.final_rating for r in results.values()]
    avg_r   = round(sum(ratings) / len(ratings), 1) if ratings else None
    max_r   = max(ratings) if ratings else None


    # Поиск по ISIN
    st.markdown('<div class="rr-search-wrap">', unsafe_allow_html=True)
    search = st.text_input("search", placeholder="🔍  Поиск по ISIN...", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

    filtered = [i for i in isins if search.strip().upper() in i.upper()] if search.strip() else isins

    if not filtered:
        st.markdown('<div style="color:#4A6B8A;padding:20px 0;font-size:13px">Ничего не найдено</div>',
                    unsafe_allow_html=True)
        return

    # Шапка таблицы
    st.markdown("""
    <div class="rr-th">
        <span class="rr-th-main">ISIN</span>
        <span class="rr-th-main">Рейтинг</span>
        <span class="rr-th-info">VaR</span>
        <span class="rr-th-info">Стресс</span>
        <span class="rr-th-info">Кредит</span>
        <span class="rr-th-info">Ставка</span>
        <span></span>
    </div>
    """, unsafe_allow_html=True)

    _COMP_KEYS = ["VaR", "StressTest", "CreditRisk", "InterestRateRisk"]

    for isin in filtered:
        row_left, row_btn = st.columns([13, 1])

        if isin not in results:
            with row_left:
                st.markdown(f'<div class="rr-row"><span class="rr-isin">{isin}</span>'
                            f'<span style="color:#4A6B8A;font-size:12px">ошибка загрузки</span></div>',
                            unsafe_allow_html=True)
            continue

        result = results[isin]
        cm = {c.component: c for c in result.components}
        fr = result.final_rating
        fc = _CLR.get(fr, "#64748B")

        info_badges = "".join(
            f'<span class="rr-badge" style="background:{_CLR.get(cm[k].rating,"#334155")}">{cm[k].rating}</span>'
            if k in cm else '<span style="color:#2D4A66;font-size:12px">—</span>'
            for k in _COMP_KEYS
        )

        with row_left:
            st.markdown(f"""
            <div class="rr-row" style="border-left-color:{fc}">
                <span class="rr-isin">{isin}</span>
                <span class="rr-rating-cell">
                    {_badge(fr)}
                    <span class="rr-rating-label" style="color:{fc}">{_RISK_LABEL.get(fr,'')}</span>
                </span>
                {info_badges}
                <span></span>
            </div>
            """, unsafe_allow_html=True)

        with row_btn:
            st.markdown("<div style='margin-top:7px'>", unsafe_allow_html=True)
            if st.button("→", key=f"go_{isin}"):
                st.session_state.selected = isin
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

# ── Детали ────────────────────────────────────────────────────────────────────

def show_detail(isin: str):
    back_col, _ = st.columns([2, 10])
    with back_col:
        if st.button("← К списку продуктов"):
            st.session_state.selected = None
            st.rerun()

    try:
        result, portfolio = _compute(isin)
    except Exception as exc:
        st.error(f"Ошибка расчёта: {exc}")
        return

    fr = result.final_rating
    fc = _CLR.get(fr, "#64748B")
    cm = {c.component: c for c in result.components}

    var_loss = ""
    if "VaR" in cm and cm["VaR"].loss_pct:
        var_loss = f"&nbsp;·&nbsp; Исторический VaR (1 год, 95%): <b>{cm['VaR'].loss_pct*100:.1f}%</b>"

    st.markdown(f"""
    <div class="rr-detail-header">
        <div>
            <div class="rr-detail-isin">{isin}</div>
            <div class="rr-detail-meta">Облигационный фонд{var_loss}</div>
        </div>
        <div class="rr-detail-right">
            <div class="rr-detail-rlabel">Итоговый рейтинг</div>
            {_badge(fr, large=True)}
            <div class="rr-detail-rname" style="color:{fc}">{_RISK_LABEL.get(fr,'')}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Компоненты
    st.markdown('<div class="rr-section">Компоненты риска</div>', unsafe_allow_html=True)
    cards = '<div class="rr-comp-grid">'
    for comp in result.components:
        c  = _CLR.get(comp.rating, "#334155")
        lbl = _COMP_LABEL.get(comp.component, comp.component)
        sub = f"потери: {comp.loss_pct*100:.1f}%" if comp.loss_pct else ""
        cards += f"""
        <div class="rr-comp-card" style="border:1px solid {c}40">
            <div style="position:absolute;top:0;left:0;right:0;height:3px;background:{c}"></div>
            <div class="rr-comp-label">{lbl}</div>
            <div class="rr-comp-num" style="color:{c}">{comp.rating}</div>
            <div class="rr-comp-sub">{sub}</div>
        </div>"""
    cards += '</div>'
    st.markdown(cards, unsafe_allow_html=True)

    # Диаграмма
    from risk_module.core.visualizer import plot_risk_result
    fig = plot_risk_result(result)
    fig.update_layout(width=None, height=370, paper_bgcolor="#0D1B2E",
                      plot_bgcolor="#0D1B2E", margin=dict(l=20, r=20, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # Холдинги
    if portfolio.holdings:
        st.markdown('<div class="rr-section" style="margin-top:24px">Состав портфеля</div>',
                    unsafe_allow_html=True)
        rows = [{"ISIN": h.isin, "Вес, %": round(h.weight * 100, 2)} for h in portfolio.holdings]
        for comp in result.components:
            if "holdings" not in comp.meta:
                continue
            by_isin = {h["isin"]: h for h in comp.meta["holdings"]}
            for row in rows:
                info = by_isin.get(row["ISIN"])
                if not info:
                    continue
                if comp.component == "CreditRisk":
                    row["СКК"] = info.get("skk", "")
                    row["Рейтинг агентства"] = f"{str(info.get('agency','')).upper()} {info.get('rating','')}"
                elif comp.component == "InterestRateRisk":
                    row["Дюрация (лет)"] = round(info.get("duration", 0), 2)
        df = pd.DataFrame(rows).sort_values("Вес, %", ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True, height=320)

    # Детали
    st.markdown('<div class="rr-section" style="margin-top:24px">Детали компонент</div>',
                unsafe_allow_html=True)
    for comp in result.components:
        lbl = _COMP_LABEL.get(comp.component, comp.component)
        with st.expander(f"{lbl}  ·  рейтинг {comp.rating}"):
            meta_top = {k: v for k, v in comp.meta.items() if k != "holdings"}
            if meta_top:
                st.json(meta_top)
            if "holdings" in comp.meta and comp.meta["holdings"]:
                st.dataframe(pd.DataFrame(comp.meta["holdings"]),
                             use_container_width=True, hide_index=True)

# ── Router ────────────────────────────────────────────────────────────────────

if st.session_state.selected is None:
    show_list()
else:
    show_detail(st.session_state.selected)

st.markdown("</div>", unsafe_allow_html=True)
