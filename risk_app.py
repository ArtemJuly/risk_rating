import os
import pathlib
import requests
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

# ── Пароль-гейт (только для тестового окружения) ─────────────────────────────
_RISK_PASSWORD = os.environ.get("RISK_PASSWORD", "")
if _RISK_PASSWORD:
    if not st.session_state.get("_auth"):
        st.markdown("""
        <style>
        .block-container { max-width: 380px !important; padding-top: 80px !important; }
        </style>
        """, unsafe_allow_html=True)
        st.markdown("### 🐊 Kroko Capital · Risk Rating")
        st.markdown("<p style='color:#8AAD99;font-size:13px'>Внутренний доступ</p>",
                    unsafe_allow_html=True)
        pwd = st.text_input("Пароль", type="password", key="_pwd_input")
        if st.button("Войти"):
            if pwd == _RISK_PASSWORD:
                st.session_state["_auth"] = True
                st.rerun()
            else:
                st.error("Неверный пароль")
        st.stop()

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 !important; max-width: 100% !important; }
section[data-testid="stSidebar"] { display: none; }

/* ── Шапка ─────────────────────────────────────────────────────── */
.rr-header {
    background: #FFFFFF;
    border-bottom: 1px solid #D9EDDF;
    padding: 16px 40px;
    display: flex; align-items: center; justify-content: space-between;
}
.rr-brand { display: flex; align-items: center; gap: 14px; }
.rr-logo {
    width: 40px; height: 40px;
    background: linear-gradient(135deg, #0C7A56, #14A072);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; line-height: 1;
}
.rr-brand-name { font-size: 20px; font-weight: 800; color: #1A2B23; letter-spacing: -0.4px; }
.rr-brand-sub  { font-size: 11px; color: #8AAD99; text-transform: uppercase; letter-spacing: 1.2px; margin-top: 1px; }
.rr-header-tag {
    background: #EBF5EF; border: 1px solid #C0DCCB;
    border-radius: 20px; padding: 4px 14px;
    font-size: 11px; color: #0C7A56; font-weight: 600; letter-spacing: 0.3px;
}

/* ── Body ───────────────────────────────────────────────────────── */
.rr-body { padding: 28px 40px 60px; }

/* ── Инфо-панель ─────────────────────────────────────────────────── */
.rr-info {
    background: #FFFFFF;
    border: 1px solid #D9EDDF;
    border-radius: 12px;
    padding: 22px 28px 20px;
    margin-bottom: 28px;
}
.rr-info-title { font-size: 11px; font-weight: 700; color: #0C7A56; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
.rr-info-text  { font-size: 13px; color: #537165; line-height: 1.7; max-width: 760px; margin-bottom: 18px; }
.rr-info-text b { color: #1A2B23; }

/* Шкала рейтинга */
.rr-scale { display: flex; gap: 6px; }
.rr-scale-item {
    flex: 1;
    border-radius: 8px;
    padding: 10px 8px 9px;
    text-align: center;
    border: 1px solid transparent;
    background: #F4FAF7;
}
.rr-scale-num  { font-size: 18px; font-weight: 800; line-height: 1; margin-bottom: 4px; }
.rr-scale-name { font-size: 10px; color: #537165; line-height: 1.3; }
.rr-scale-loss { font-size: 9.5px; color: #8AAD99; margin-top: 3px; font-family: 'JetBrains Mono', monospace; }

/* ── Поиск ──────────────────────────────────────────────────────── */
.rr-search-wrap { margin-bottom: 20px; }
div[data-testid="stTextInput"] label { display: none !important; }
div[data-testid="stTextInput"] > div { margin-top: 0 !important; }
div[data-testid="stTextInput"] input {
    background: #FFFFFF !important;
    border: 1px solid #C0DCCB !important;
    border-radius: 8px !important;
    color: #1A2B23 !important;
    font-size: 14px !important;
}
div[data-testid="stTextInput"] input:focus { border-color: #0C7A56 !important; box-shadow: 0 0 0 3px #0C7A5618 !important; }

/* ── Карточка бумаги ─────────────────────────────────────────────── */
.bond-card {
    background: #FFFFFF;
    border: 1px solid #D9EDDF;
    border-radius: 12px;
    padding: 22px 24px 18px;
    margin-bottom: 2px;
    height: 100%;
    box-shadow: 0 1px 4px rgba(12, 122, 86, 0.06);
}

/* Шапка карточки: большой рейтинг слева + иден. справа */
.card-head { display: flex; align-items: flex-start; gap: 18px; margin-bottom: 16px; }
.card-rating-block { flex-shrink: 0; text-align: center; }
.card-rating-num {
    width: 52px; height: 52px;
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 26px; font-weight: 800; color: #FFFFFF;
    margin-bottom: 4px;
}
.card-rating-txt { font-size: 10px; color: #8AAD99; line-height: 1.25; text-align: center; max-width: 52px; }

.card-id { flex: 1; min-width: 0; }
.card-name { font-size: 14px; font-weight: 700; color: #1A2B23; margin-bottom: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-isin {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11.5px; color: #8AAD99; font-weight: 600;
    letter-spacing: 0.3px; margin-bottom: 8px;
}
.card-pills { display: flex; flex-wrap: wrap; gap: 5px; }
.pill {
    display: inline-flex; align-items: center;
    background: #EBF5EF; border-radius: 5px;
    padding: 2px 8px;
    font-size: 11px; color: #0C7A56; font-weight: 600;
}
.pill-yield {
    background: #FEF9E7; color: #B85C00;
}
.pill-date { background: #F0F3FF; color: #3A56C4; }
.pill-cur  { background: #EBF5EF; color: #0C7A56; }

/* Разделитель */
.card-divider { border: none; border-top: 1px solid #EBF5EF; margin: 14px 0; }

/* Метрики под разделителем */
.card-metrics { display: flex; gap: 6px; }
.metric-item {
    flex: 1;
    background: #F4FAF7;
    border-radius: 8px;
    padding: 8px 6px;
    text-align: center;
}
.metric-label { font-size: 9.5px; color: #8AAD99; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px; }
.metric-dot {
    display: inline-flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; border-radius: 7px;
    font-size: 14px; font-weight: 800; color: #FFFFFF;
}
.metric-dash { font-size: 18px; color: #C0DCCB; font-weight: 300; }

/* ── Кнопки ─────────────────────────────────────────────────────── */
.stButton > button {
    background: #F4FAF7 !important;
    border: 1px solid #C0DCCB !important;
    border-radius: 8px !important;
    color: #0C7A56 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 5px 16px !important;
    width: 100% !important;
    transition: all 0.12s !important;
}
.stButton > button:hover {
    background: #0C7A56 !important;
    border-color: #0C7A56 !important;
    color: #FFFFFF !important;
}

/* ── Страница детали ─────────────────────────────────────────────── */
.rr-detail-header {
    background: #FFFFFF;
    border: 1px solid #D9EDDF;
    border-radius: 12px;
    padding: 28px 32px;
    margin-bottom: 20px;
    box-shadow: 0 1px 4px rgba(12, 122, 86, 0.06);
}
.rr-detail-name  { font-size: 22px; font-weight: 800; color: #1A2B23; margin-bottom: 4px; }
.rr-detail-isin  { font-family: 'JetBrains Mono', monospace; font-size: 13px; color: #8AAD99; margin-bottom: 14px; }
.rr-detail-facts { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }
.detail-fact {
    background: #F4FAF7; border: 1px solid #D9EDDF;
    border-radius: 8px; padding: 8px 14px;
}
.detail-fact-label { font-size: 10px; color: #8AAD99; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 3px; }
.detail-fact-value { font-size: 15px; font-weight: 700; color: #1A2B23; }

.rr-detail-issuer {
    background: #EBF5EF;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px; color: #537165; line-height: 1.6;
}
.rr-detail-issuer b { color: #0C7A56; }

/* Итоговый рейтинг в детали */
.rr-final-block {
    display: flex; align-items: center; gap: 14px;
    padding: 16px 20px;
    background: #F4FAF7; border: 1px solid #D9EDDF;
    border-radius: 10px; margin-bottom: 20px;
}
.rr-final-num {
    width: 56px; height: 56px; border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 28px; font-weight: 800; color: #FFFFFF; flex-shrink: 0;
}
.rr-final-label { font-size: 13px; color: #8AAD99; margin-bottom: 2px; }
.rr-final-name  { font-size: 18px; font-weight: 700; color: #1A2B23; }
.rr-final-hint  { font-size: 12px; color: #8AAD99; margin-top: 4px; }

/* Сетка компонент */
.rr-comp-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 16px 0 24px; }
.rr-comp-card {
    background: #FFFFFF; border: 1px solid #D9EDDF;
    border-radius: 10px; padding: 18px 14px; text-align: center;
    position: relative; overflow: hidden;
}
.rr-comp-top  { position: absolute; top: 0; left: 0; right: 0; height: 3px; }
.rr-comp-label { font-size: 10px; color: #8AAD99; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 10px; }
.rr-comp-num  { font-size: 46px; font-weight: 800; line-height: 1; margin-bottom: 4px; }
.rr-comp-sub  { font-size: 11px; color: #8AAD99; }

/* Секция-заголовок */
.rr-section {
    font-size: 11px; font-weight: 700; color: #0C7A56;
    text-transform: uppercase; letter-spacing: 1px;
    padding-bottom: 10px; border-bottom: 1px solid #D9EDDF;
    margin-bottom: 14px;
}

.stDataFrame { border: 1px solid #D9EDDF !important; border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

# ── Справочники ───────────────────────────────────────────────────────────────

_CLR = {
    1: "#16A34A", 2: "#65A30D", 3: "#CA8A04",
    4: "#EA580C", 5: "#DC2626", 6: "#B91C1C", 7: "#7F1D1D",
}
_RISK_LABEL = {
    1: "Минимальный", 2: "Низкий", 3: "Умеренно низкий",
    4: "Умеренный",   5: "Умеренно высокий", 6: "Высокий", 7: "Максимальный",
}
_LOSS_RANGE = {1: "0–5%", 2: "5–10%", 3: "10–20%", 4: "20–30%", 5: "30–50%", 6: "50–70%", 7: ">70%"}
_COMP_LABEL = {
    "VaR": "VaR",
    "StressTest": "Стресс",
    "CreditRisk": "Кредит",
    "InterestRateRisk": "Дюрация",
    "LiquidityRisk": "Ликвидность",
    "IssueQuality": "Качество",
}

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


# Заглушки — заменить на реальные данные при подключении источника
_PLACEHOLDER: dict[str, dict] = {
    "RU000A1002D0": {
        "name":     "Альфа-Банк, БО-06",
        "issuer":   "АО «Альфа-Банк»",
        "type":     "Биржевая облигация",
        "currency": "RUB",
        "maturity": "2027-04-14",
        "coupon":   9.40,
        "yield":    16.8,
        "description": (
            "АО «Альфа-Банк» — один из крупнейших частных банков России. "
            "Входит в состав Альфа-Групп. Рейтинг А+ (АКРА), А+ (Эксперт РА). "
            "Специализируется на корпоративном и розничном кредитовании."
        ),
    },
    "RU000A1002S8": {
        "name":     "Газпром капитал, 003Р-02",
        "issuer":   "ООО «Газпром капитал»",
        "type":     "Биржевая облигация",
        "currency": "RUB",
        "maturity": "2028-11-22",
        "coupon":   8.50,
        "yield":    17.2,
        "description": (
            "ООО «Газпром капитал» — финансовая «дочка» ПАО «Газпром», "
            "основной инструмент группы для привлечения рублёвых заимствований. "
            "Рейтинг ААА (АКРА). Поручительство материнской компании."
        ),
    },
    "RU000A105QR3": {
        "name":     "РЖД, 001Р-24R",
        "issuer":   "ОАО «РЖД»",
        "type":     "Биржевая облигация",
        "currency": "RUB",
        "maturity": "2030-06-07",
        "coupon":   10.85,
        "yield":    15.9,
        "description": (
            "ОАО «Российские железные дороги» — государственная монополия, "
            "100% принадлежит государству. Рейтинг ААА (АКРА, Эксперт РА). "
            "Крупнейший нефинансовый эмитент на российском облигационном рынке."
        ),
    },
}


@st.cache_data(show_spinner=False, ttl=3600)
def _fund_meta(isin: str) -> dict:
    """Параметры бумаги: сначала MOEX ISS, затем заглушка."""
    try:
        r = requests.get(
            f"https://iss.moex.com/iss/securities/{isin}.json",
            params={"iss.meta": "off", "iss.only": "description"},
            timeout=8,
        )
        desc = {row[0]: row[2] for row in r.json().get("description", {}).get("data", [])}
        if desc.get("NAME"):
            placeholder = _PLACEHOLDER.get(isin, {})
            return {
                "name":        desc.get("NAME"),
                "issuer":      desc.get("EMITENT_TITLE") or placeholder.get("issuer", ""),
                "maturity":    desc.get("MATDATE"),
                "currency":    desc.get("FACEUNIT") or "RUB",
                "coupon":      desc.get("COUPONVALUE"),
                "type":        desc.get("TYPENAME") or "",
                "description": placeholder.get("description", ""),
            }
    except Exception:
        pass
    # Заглушка
    p = _PLACEHOLDER.get(isin, {})
    return {
        "name":        p.get("name", isin),
        "issuer":      p.get("issuer", ""),
        "maturity":    p.get("maturity"),
        "currency":    p.get("currency", "RUB"),
        "coupon":      p.get("coupon"),
        "type":        p.get("type", ""),
        "description": p.get("description", ""),
    }


@st.cache_data(show_spinner=False, ttl=3600)
def _fund_yield(isin: str) -> float | None:
    """Текущая доходность: MOEX ISS → заглушка."""
    try:
        for board in ["TQCB", "TQOB", "TQOD"]:
            r = requests.get(
                f"https://iss.moex.com/iss/engines/stock/markets/bonds/boards/{board}/securities/{isin}.json",
                params={"marketdata.columns": "YIELD", "iss.only": "marketdata", "iss.meta": "off"},
                timeout=8,
            )
            data = r.json().get("marketdata", {})
            rows = data.get("data", [])
            if rows and rows[0] and rows[0][0] is not None:
                return float(rows[0][0])
    except Exception:
        pass
    # Заглушка
    return _PLACEHOLDER.get(isin, {}).get("yield")


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
  <div class="rr-header-tag">Аналитика рисков · Внутренняя платформа</div>
</div>
<div class="rr-body">
""", unsafe_allow_html=True)


# ── Инфо-панель ───────────────────────────────────────────────────────────────

def _info_panel():
    scale_items = "".join(f"""
    <div class="rr-scale-item" style="border-color:{_CLR[r]}30">
        <div class="rr-scale-num" style="color:{_CLR[r]}">{r}</div>
        <div class="rr-scale-name">{_RISK_LABEL[r]}</div>
        <div class="rr-scale-loss">{_LOSS_RANGE[r]}</div>
    </div>""" for r in range(1, 8))

    st.markdown(f"""
    <div class="rr-info">
        <div class="rr-info-title">Шкала риск-рейтинга</div>
        <div class="rr-info-text">
            Риск-рейтинг — интегральная оценка от <b>1 (минимальный)</b> до <b>7 (максимальный)</b>.
            Итоговый рейтинг равен <b>максимуму</b> всех компонент: кредитного риска, процентного риска,
            VaR и стресс-теста. Компонентные оценки показывают, <b>какой именно риск</b> является определяющим.
        </div>
        <div class="rr-scale">{scale_items}</div>
    </div>
    """, unsafe_allow_html=True)


def _issuer_block(meta: dict, typ: str) -> str:
    desc = meta.get("description", "")
    issuer = meta.get("issuer", "")
    if desc:
        label = f"<b>{issuer or typ}</b> · " if (issuer or typ) else ""
        return f"{label}{desc}"
    fallback = issuer or typ or "Долговой инструмент"
    return f"<b>{fallback}</b> · Расчёт по данным MOEX ISS и внутренней базе облигаций."


# ── Рендер карточки ────────────────────────────────────────────────────────────

def _render_metric(label: str, rating: int | None) -> str:
    if rating is None:
        return f"""<div class="metric-item">
            <div class="metric-label">{label}</div>
            <div class="metric-dash">—</div>
        </div>"""
    c = _CLR.get(rating, "#94A3B8")
    return f"""<div class="metric-item">
        <div class="metric-label">{label}</div>
        <div class="metric-dot" style="background:{c}">{rating}</div>
    </div>"""


def _card_html(isin: str, result, meta: dict, yld: float | None) -> str:
    fr   = result.final_rating if result else None
    cm   = {c.component: c for c in result.components} if result else {}
    fc   = _CLR.get(fr, "#94A3B8") if fr else "#94A3B8"
    name = meta.get("name") or isin
    cur  = meta.get("currency") or "RUB"
    mat  = meta.get("maturity") or ""
    if mat and len(str(mat)) >= 10:
        mat = str(mat)[:10]

    pills = f'<span class="pill pill-cur">{cur}</span>'
    if mat:
        pills += f'<span class="pill pill-date">до {mat}</span>'
    if yld is not None:
        pills += f'<span class="pill pill-yield">{yld:.1f}%</span>'

    rating_block = (
        f'<div class="card-rating-num" style="background:{fc}">{fr}</div>'
        f'<div class="card-rating-txt">{_RISK_LABEL.get(fr, "")}</div>'
        if fr else
        '<div class="card-rating-num" style="background:#CBD5E1">—</div>'
        '<div class="card-rating-txt">нет данных</div>'
    )

    # Три ключевых метрики
    liq    = cm.get("LiquidityRisk")
    credit = cm.get("CreditRisk") or cm.get("IssueQuality")
    market = cm.get("VaR")

    liq_r    = liq.rating    if liq    else None
    credit_r = credit.rating if credit else None
    market_r = market.rating if market else None

    return f"""
    <div class="bond-card">
        <div class="card-head">
            <div class="card-rating-block">
                {rating_block}
            </div>
            <div class="card-id">
                <div class="card-name" title="{name}">{name}</div>
                <div class="card-isin">{isin}</div>
                <div class="card-pills">{pills}</div>
            </div>
        </div>
        <hr class="card-divider">
        <div class="card-metrics">
            {_render_metric("Ликвидность", liq_r)}
            {_render_metric("Кред. риск", credit_r)}
            {_render_metric("Рын. риск", market_r)}
        </div>
    </div>
    """


# ── Список ────────────────────────────────────────────────────────────────────

def show_list():
    isins = _available_isins()
    if not isins:
        st.warning("Нет файлов в data/products/")
        return

    _info_panel()

    # Предзагрузка рейтингов
    results = {}
    for isin in isins:
        try:
            results[isin], _ = _compute(isin)
        except Exception:
            pass

    # Поиск
    st.markdown('<div class="rr-search-wrap">', unsafe_allow_html=True)
    search = st.text_input("search", placeholder="🔍  Поиск по ISIN или названию...", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

    filtered = (
        [i for i in isins if search.strip().upper() in i.upper()]
        if search.strip() else isins
    )

    if not filtered:
        st.markdown('<div style="color:#8AAD99;padding:20px 0;font-size:13px">Ничего не найдено</div>',
                    unsafe_allow_html=True)
        return

    # Сетка 2 колонки
    for i in range(0, len(filtered), 2):
        cols = st.columns(2, gap="medium")
        for j, col in enumerate(cols):
            if i + j >= len(filtered):
                break
            isin   = filtered[i + j]
            result = results.get(isin)
            meta   = _fund_meta(isin)
            yld    = _fund_yield(isin)

            with col:
                st.markdown(_card_html(isin, result, meta, yld), unsafe_allow_html=True)
                if st.button("Подробнее →", key=f"go_{isin}"):
                    st.session_state.selected = isin
                    st.rerun()
            st.markdown("")  # небольшой отступ


# ── Детали ────────────────────────────────────────────────────────────────────

def show_detail(isin: str):
    back_col, _ = st.columns([2, 10])
    with back_col:
        if st.button("← К списку"):
            st.session_state.selected = None
            st.rerun()

    try:
        result, portfolio = _compute(isin)
    except Exception as exc:
        st.error(f"Ошибка расчёта: {exc}")
        return

    meta = _fund_meta(isin)
    yld  = _fund_yield(isin)

    fr = result.final_rating
    fc = _CLR.get(fr, "#94A3B8")
    cm = {c.component: c for c in result.components}

    name    = meta.get("name") or isin
    cur     = meta.get("currency") or "RUB"
    mat     = str(meta.get("maturity") or "")[:10] or "—"
    typ     = meta.get("type") or "Долговой инструмент"
    coupon  = meta.get("coupon")
    var_pct = cm["VaR"].loss_pct * 100 if "VaR" in cm and cm["VaR"].loss_pct else None

    # Шапка
    coupon_str = f"{coupon:.2f}%" if coupon else "—"
    yield_str  = f"{yld:.2f}%" if yld is not None else "—"
    var_str    = f"{var_pct:.1f}%" if var_pct is not None else "—"

    irr_dur = None
    if "InterestRateRisk" in cm:
        holdings = cm["InterestRateRisk"].meta.get("holdings", [])
        if holdings:
            irr_dur = cm["InterestRateRisk"].meta.get("weighted_avg_duration")

    dur_str = f"{irr_dur:.2f} лет" if irr_dur else "—"

    facts = [
        ("Валюта",         cur),
        ("Погашение",      mat),
        ("Ставка купона",  coupon_str),
        ("Доходность",     yield_str),
        ("Дюрация",        dur_str),
        ("VaR (95%, 1г)",  var_str),
    ]
    facts_html = "".join(f"""
        <div class="detail-fact">
            <div class="detail-fact-label">{lbl}</div>
            <div class="detail-fact-value">{val}</div>
        </div>""" for lbl, val in facts)

    st.markdown(f"""
    <div class="rr-detail-header">
        <div class="rr-detail-name">{name}</div>
        <div class="rr-detail-isin">{isin}</div>
        <div class="rr-detail-facts">{facts_html}</div>
        <div class="rr-detail-issuer">{_issuer_block(meta, typ)}</div>
    </div>
    """, unsafe_allow_html=True)

    # Итоговый рейтинг
    st.markdown(f"""
    <div class="rr-final-block">
        <div class="rr-final-num" style="background:{fc}">{fr}</div>
        <div>
            <div class="rr-final-label">Итоговый риск-рейтинг</div>
            <div class="rr-final-name" style="color:{fc}">{_RISK_LABEL.get(fr,'')}</div>
            <div class="rr-final-hint">Ожидаемые потери в стрессовом сценарии: {_LOSS_RANGE.get(fr,'—')}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Компоненты
    st.markdown('<div class="rr-section">Компоненты риска</div>', unsafe_allow_html=True)
    cards = '<div class="rr-comp-grid">'
    for comp in result.components:
        c   = _CLR.get(comp.rating, "#94A3B8")
        lbl = _COMP_LABEL.get(comp.component, comp.component)
        sub = f"потери: {comp.loss_pct*100:.1f}%" if comp.loss_pct else ""
        cards += f"""
        <div class="rr-comp-card">
            <div class="rr-comp-top" style="background:{c}"></div>
            <div class="rr-comp-label">{lbl}</div>
            <div class="rr-comp-num" style="color:{c}">{comp.rating}</div>
            <div class="rr-comp-sub">{sub}</div>
        </div>"""
    cards += "</div>"
    st.markdown(cards, unsafe_allow_html=True)

    # Диаграмма
    from risk_module.core.visualizer import plot_risk_result
    fig = plot_risk_result(result)
    fig.update_layout(
        width=None, height=340,
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        margin=dict(l=20, r=20, t=40, b=10),
        font=dict(color="#1A2B23"),
    )
    fig.update_xaxes(gridcolor="#EBF5EF", zerolinecolor="#D9EDDF")
    fig.update_yaxes(gridcolor="#EBF5EF", zerolinecolor="#D9EDDF")
    st.plotly_chart(fig, use_container_width=True)

    # Холдинги
    if portfolio.holdings:
        st.markdown('<div class="rr-section" style="margin-top:8px">Состав портфеля</div>',
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
                    row["Рейтинг"] = f"{str(info.get('agency','')).upper()} {info.get('rating','')}"
                elif comp.component == "InterestRateRisk":
                    row["Дюрация (лет)"] = round(info.get("duration", 0), 2)
        df = pd.DataFrame(rows).sort_values("Вес, %", ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True, height=300)

    # Детали
    st.markdown('<div class="rr-section" style="margin-top:8px">Детали компонент</div>',
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
