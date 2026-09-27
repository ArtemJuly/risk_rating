import os
import pathlib
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = pathlib.Path(__file__).parent
DATA_DIR = BASE_DIR / "data"


def _load_fund_catalog() -> dict[str, dict]:
    """Единственный источник правды о том, что показывать на сайте.

    data/reference/funds.csv: ISIN,Ticker,Name — добавить/убрать инструмент
    значит добавить/убрать строку в этом файле, больше нигде трогать не надо.
    """
    path = DATA_DIR / "reference" / "funds.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str).fillna("")
    return {
        row["ISIN"].strip(): {"ticker": row["Ticker"].strip(), "name": row["Name"].strip()}
        for _, row in df.iterrows()
        if row["ISIN"].strip()
    }


_FUND_CATALOG = _load_fund_catalog()

st.set_page_config(
    page_title="Kroko Capital · Кроко Рейтинг",
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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@600;700&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; background: #0B0F14 !important; color: #EDF1F5 !important; }
        .block-container { max-width: 360px !important; padding-top: 130px !important; }
        #MainMenu, footer, header { visibility: hidden; }
        section[data-testid="stSidebar"] { display: none; }
        .gate-logo {
            width: 64px; height: 64px; margin: 0 auto 22px;
            background: linear-gradient(155deg, #16211C, #0F1712);
            border: 1px solid #2DD4BF44;
            border-radius: 18px;
            display: flex; align-items: center; justify-content: center;
            font-size: 32px;
            box-shadow: 0 0 0 1px #0B0F14, 0 8px 24px rgba(45,212,191,0.14);
        }
        .gate-title { font-family: 'Space Grotesk', sans-serif; font-size: 19px; font-weight: 700; color: #EDF1F5; text-align: center; letter-spacing: -0.2px; }
        .gate-sub { font-size: 13px; color: #7A8894; text-align: center; margin-top: 4px; margin-bottom: 28px; }
        div[data-testid="stTextInput"] input {
            background: #131A21 !important; color: #EDF1F5 !important;
            border-radius: 10px !important; padding: 11px 14px !important;
            border: 1px solid #253039 !important;
        }
        .stButton > button {
            width: 100% !important; border-radius: 10px !important;
            background: #2DD4BF !important; color: #08211C !important;
            border: none !important; font-weight: 700 !important; padding: 10px !important;
        }
        .stButton > button:hover { background: #5EEAD4 !important; }
        </style>
        <div class="gate-logo">🐊</div>
        <div class="gate-title">Kroko Capital · Кроко Рейтинг</div>
        <div class="gate-sub">Внутренний доступ</div>
        """, unsafe_allow_html=True)
        pwd = st.text_input("Пароль", type="password", key="_pwd_input", label_visibility="collapsed",
                             placeholder="Пароль")
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── Референс: доход.рф — светлый серый фон, белые карточки с тенью,
   жирная чёрная типографика, зелёный акцент бренда ─────────────── */
:root {
  --bg:         #EBEBED;
  --surface:    #FFFFFF;
  --surface-2:  #F5F5F7;
  --border:     #E3E3E6;
  --text-1:     #111111;
  --text-2:     #555555;
  --text-3:     #AAAAAA;
  --accent:     #0A7A54;
  --acc-dim:    rgba(10,122,84,0.08);
  --acc-border: rgba(10,122,84,0.28);
  --acc-glow:   rgba(10,122,84,0.13);
  --shadow-sm:  0 1px 6px rgba(0,0,0,0.06);
  --shadow-md:  0 3px 14px rgba(0,0,0,0.08);
  --shadow-lg:  0 6px 24px rgba(0,0,0,0.10);
}

html, body, [class*="css"],
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"],
[data-testid="stMainBlockContainer"], section.main {
  font-family: 'Inter', sans-serif;
  background: var(--bg) !important;
  color: var(--text-1) !important;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container,
[data-testid="stMainBlockContainer"],
[data-testid="stAppViewBlockContainer"] {
    padding: 0 !important; max-width: 100% !important; background: var(--bg) !important;
}
section[data-testid="stSidebar"] { display: none; }
[data-testid="stAlert"] {
    background: var(--surface) !important; border: none !important;
    box-shadow: var(--shadow-sm) !important;
    color: var(--text-1) !important; border-radius: 12px !important;
}

/* ── Шапка ─────────────────────────────────────────────────────── */
.rr-header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 16px 56px;
    display: flex; align-items: center; justify-content: space-between;
    position: sticky; top: 0; z-index: 100;
    box-shadow: var(--shadow-sm);
}
.rr-brand { display: flex; align-items: center; gap: 14px; }
.rr-logo {
    width: 44px; height: 44px; flex-shrink: 0;
    background: linear-gradient(135deg, #065F46, #16A374);
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px;
    box-shadow: 0 2px 10px rgba(10,122,84,0.20);
}
.rr-brand-name { font-size: 19px; font-weight: 800; color: var(--text-1); letter-spacing: -0.4px; }
.rr-brand-sub  { font-size: 10px; color: var(--text-3); text-transform: uppercase; letter-spacing: 1.8px; margin-top: 2px; font-weight: 600; }
.rr-header-tag {
    background: var(--acc-dim);
    border: 1px solid var(--acc-border);
    border-radius: 20px; padding: 5px 14px;
    font-size: 12px; color: var(--accent); font-weight: 600;
}

/* ── Body ───────────────────────────────────────────────────────── */
.rr-body { padding: 20px 56px 80px; }

/* ── Топ-бар: счётчик + шкала ───────────────────────────────────── */
.rr-topbar {
    background: var(--surface);
    border-radius: 16px;
    box-shadow: var(--shadow-sm);
    padding: 22px 28px;
    margin-bottom: 24px;
}
.rr-count { font-size: 13px; color: var(--text-3); margin-bottom: 18px; }
.rr-count b { color: var(--text-1); font-weight: 800; font-size: 16px; }

.rr-scale-strip { display: flex; gap: 8px; }
.rr-scale-cell {
    flex: 1; border-radius: 10px; padding: 10px 8px 9px;
    background: var(--surface-2); text-align: center;
    border-top: 3px solid; border-left: 1px solid var(--border);
    border-right: 1px solid var(--border); border-bottom: 1px solid var(--border);
}
.rr-scale-n    { font-size: 20px; font-weight: 800; line-height: 1; margin-bottom: 4px; }
.rr-scale-lbl  { font-size: 9px; color: var(--text-2); line-height: 1.35; }
.rr-scale-loss { font-size: 9px; color: var(--text-3); margin-top: 3px;
                  font-family: 'JetBrains Mono', monospace; }

.rr-topbar-divider { height: 1px; background: var(--border); margin: 20px 0 16px; }
.rr-topbar-about { display: flex; align-items: baseline; justify-content: space-between; gap: 32px; }
.rr-topbar-desc {
    font-size: 13px; color: var(--text-2); line-height: 1.65; flex: 1;
}
.rr-topbar-disclaimer {
    font-size: 11px; color: var(--text-3); white-space: nowrap;
    font-style: italic; flex-shrink: 0;
}

/* ── Поиск + фильтр ─────────────────────────────────────────────── */
div[data-testid="stTextInput"] label { display: none !important; }
div[data-testid="stTextInput"] > div { margin-top: 0 !important; }
div[data-testid="stTextInput"] input {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-1) !important;
    font-size: 15px !important;
    padding: 11px 16px !important;
    box-shadow: var(--shadow-sm) !important;
}
div[data-testid="stTextInput"] input::placeholder { color: var(--text-3) !important; }
div[data-testid="stTextInput"] input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--acc-glow) !important;
    outline: none !important;
}

div[data-testid="stMultiSelect"] label { display: none !important; }
div[data-testid="stMultiSelect"] > div > div {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-1) !important;
    font-size: 15px !important;
    min-height: 44px !important;
    box-shadow: var(--shadow-sm) !important;
}
div[data-testid="stMultiSelect"] > div > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--acc-glow) !important;
}
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: var(--acc-dim) !important; border: 1px solid var(--acc-border) !important;
    border-radius: 6px !important; color: var(--accent) !important;
    font-weight: 600 !important; font-size: 13px !important;
}

/* ── Таблица ─────────────────────────────────────────────────────── */

.rr-col-rating { width: 66px;  flex-shrink: 0; }
.rr-col-name   { flex: 1;      min-width: 0; }
.rr-col-ret    { width: 82px;  flex-shrink: 0; text-align: right; }
.rr-col-risk   { width: 66px;  flex-shrink: 0; text-align: center; }
.rr-col-sep    { width: 1px;   background: var(--border); align-self: stretch; margin: 0 18px; flex-shrink: 0; }

.rr-table-head {
    display: flex; align-items: center;
    padding: 8px 22px 10px;
    font-size: 10px; font-weight: 700; color: var(--text-3);
    text-transform: uppercase; letter-spacing: 0.8px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 10px;
    font-family: 'JetBrains Mono', monospace;
}
.rr-th-group { font-size: 8.5px; color: var(--text-3); letter-spacing: 0.3px; margin-bottom: 2px; opacity: 0.6; }

/* Строки-карточки в стиле ДОХОД */
.rr-row {
    display: flex; align-items: center;
    padding: 18px 22px;
    background: var(--surface);
    border-radius: 14px;
    margin-bottom: 8px;
    transition: box-shadow 0.15s, transform 0.1s;
    min-height: 88px;
    box-shadow: var(--shadow-sm);
    border: none;
}
.rr-row:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
}

/* Риск-метка */
.rr-rating { display: flex; flex-direction: column; align-items: center; gap: 5px; flex-shrink: 0; }
.rr-rating-num { font-weight: 800; line-height: 1; letter-spacing: -0.5px; }
.rr-rating-ticks { display: flex; align-items: flex-end; }
.rr-rating-ticks .tick { border-radius: 1px; flex-shrink: 0; }

.rr-row-name {
    font-size: 17px; font-weight: 700; color: var(--text-1);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block;
    letter-spacing: -0.25px;
}
.rr-row-desc {
    font-size: 13px; color: var(--text-2); margin-top: 5px;
    overflow: hidden; display: -webkit-box; -webkit-box-orient: vertical;
    -webkit-line-clamp: 2; line-height: 1.5; max-height: 3em;
}
.rr-row-sub { display: flex; align-items: center; gap: 8px; margin-top: 7px; }
.rr-row-isin { font-family: 'JetBrains Mono', monospace; font-size: 10.5px; color: var(--text-3); }
.rr-row-type {
    font-size: 10px; color: var(--accent); background: var(--acc-dim);
    border-radius: 5px; padding: 2px 8px; font-weight: 600;
}

/* Тег инструмента — как у ДОХОД */
.rr-row-tag {
    display: inline-block; font-size: 10px; font-weight: 700; letter-spacing: 0.3px;
    color: var(--text-2); background: var(--surface-2); border: 1px solid var(--border);
    border-radius: 6px; padding: 2px 8px; text-transform: uppercase;
}

.rr-ret-pos { font-size: 15px; font-weight: 700; color: #166534; font-family: 'JetBrains Mono', monospace; }
.rr-ret-neg { font-size: 15px; font-weight: 700; color: #991B1B; font-family: 'JetBrains Mono', monospace; }
.rr-ret-nil { font-size: 15px; color: var(--text-3); font-family: 'JetBrains Mono', monospace; }
.rr-ret-arrow { font-size: 9px; margin-right: 2px; opacity: 0.6; }

.rr-mini-label {
    font-size: 10px; color: var(--text-3); text-transform: uppercase;
    letter-spacing: 0.6px; margin-bottom: 5px;
    font-family: 'JetBrains Mono', monospace; font-weight: 600;
}
.rr-mini-badge {
    width: 32px; height: 32px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 15px; font-weight: 800; color: #FFFFFF; margin: 0 auto;
}
.rr-mini-dash {
    width: 32px; height: 32px; border-radius: 8px; background: var(--surface-2);
    border: 1px solid var(--border);
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; color: var(--text-3); margin: 0 auto;
}

div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stHorizontalBlock"]:has(.rr-row)) {
    margin-bottom: -8px;
}

.row-btn > button {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-3) !important;
    font-size: 20px !important;
    padding: 4px 10px !important;
    width: auto !important; min-height: 0 !important;
    height: 52px !important; border-radius: 12px !important;
    box-shadow: var(--shadow-sm) !important;
    transition: all 0.12s !important;
}
.row-btn > button:hover {
    color: var(--accent) !important;
    border-color: var(--acc-border) !important;
    box-shadow: var(--shadow-md) !important;
}

/* ── Детальная страница ──────────────────────────────────────────── */
.rr-detail-header {
    background: var(--surface); border-radius: 16px;
    padding: 32px 38px; margin-bottom: 22px;
    box-shadow: var(--shadow-sm);
}
.rr-detail-name  { font-size: 26px; font-weight: 800; color: var(--text-1); margin-bottom: 6px; letter-spacing: -0.4px; }
.rr-detail-isin  { font-family: 'JetBrains Mono', monospace; font-size: 13px; color: var(--text-3); margin-bottom: 20px; }
.rr-detail-facts { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }
.detail-fact {
    background: var(--surface-2); border: 1px solid var(--border);
    border-radius: 10px; padding: 11px 18px;
}
.detail-fact-label { font-size: 10px; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.7px; margin-bottom: 5px; }
.detail-fact-value { font-size: 17px; font-weight: 700; color: var(--text-1); }

.rr-detail-issuer {
    background: var(--acc-dim); border: 1px solid var(--acc-border);
    border-radius: 10px; padding: 14px 18px;
    font-size: 14px; color: var(--text-2); line-height: 1.75;
}
.rr-detail-issuer b { color: var(--accent); }

.rr-final-block {
    display: flex; align-items: center; gap: 24px;
    padding: 24px 28px; background: var(--surface);
    border-radius: 14px; margin-bottom: 24px; box-shadow: var(--shadow-sm);
}
.rr-final-label { font-size: 11px; color: var(--text-3); margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.9px; font-weight: 600; }
.rr-final-name  { font-size: 22px; font-weight: 700; }
.rr-final-hint  { font-size: 13px; color: var(--text-3); margin-top: 6px; }

.rr-comp-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 18px 0 28px; }
.rr-comp-card {
    background: var(--surface); border-radius: 14px;
    padding: 22px 14px 20px; text-align: center;
    position: relative; overflow: hidden;
    display: flex; flex-direction: column; align-items: center;
    box-shadow: var(--shadow-sm);
}
.rr-comp-top  { position: absolute; top: 0; left: 0; right: 0; height: 3px; }
.rr-comp-label { font-size: 10px; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.9px; margin-bottom: 14px; font-weight: 700; }
.rr-comp-sub  { font-size: 12px; color: var(--text-3); margin-top: 10px; font-family: 'JetBrains Mono', monospace; }

.rr-section {
    font-size: 11px; font-weight: 700; color: var(--accent);
    text-transform: uppercase; letter-spacing: 1.4px;
    padding-bottom: 12px; border-bottom: 1px solid var(--border); margin-bottom: 18px;
}

.rr-htable { width: 100%; border-collapse: collapse; margin-bottom: 28px; }
.rr-htable th {
    text-align: left; font-size: 11px; color: var(--text-3);
    text-transform: uppercase; letter-spacing: 0.7px; font-weight: 700;
    padding: 0 14px 10px; border-bottom: 1px solid var(--border);
}
.rr-htable th.num, .rr-htable td.num { text-align: right; }
.rr-htable td {
    font-size: 14px; color: var(--text-1); padding: 12px 14px;
    border-bottom: 1px solid var(--border);
}
.rr-htable tr:last-child td { border-bottom: none; }
.rr-htable td.isin { font-family: 'JetBrains Mono', monospace; color: var(--text-2); }
.rr-htable .wbar { display: flex; align-items: center; gap: 8px; justify-content: flex-end; }
.rr-htable .wbar-track { width: 60px; height: 4px; background: var(--surface-2); border-radius: 2px; overflow: hidden; }
.rr-htable .wbar-fill { height: 100%; background: var(--accent); border-radius: 2px; }

/* ── Кнопки ─────────────────────────────────────────────────────── */
/* ── Карточки продуктов (grid) ───────────────────────────────────── */
.rr-card {
    background: var(--surface);
    border-radius: 16px;
    box-shadow: var(--shadow-sm);
    overflow: hidden;
    transition: box-shadow 0.18s, transform 0.14s;
    display: flex; flex-direction: column;
}
.rr-card { cursor: pointer; }
/* Hover через JS — класс .rr-card-hovered вешает скрипт */
.rr-card.rr-card-hovered {
    box-shadow: var(--shadow-lg);
    transform: translateY(-3px);
}
/* Кнопка-триггер скрыта визуально, доступна для JS .click() */
[data-testid="stVerticalBlock"]:has(.rr-card) [data-testid="stButton"] {
    height: 0 !important; min-height: 0 !important;
    overflow: hidden !important; margin: 0 !important; padding: 0 !important;
}
.rr-card-img {
    height: 200px; position: relative; overflow: hidden; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
}
.rr-card-tag {
    position: absolute; top: 14px; right: 14px;
    background: rgba(255,255,255,0.88); backdrop-filter: blur(4px);
    border-radius: 7px; padding: 4px 12px;
    font-size: 11px; font-weight: 700; color: var(--text-2);
    text-transform: uppercase; letter-spacing: 0.5px;
}
/* Центральный блок рейтинга в градиентной зоне */
.rr-card-rating-center {
    display: flex; flex-direction: column; align-items: center;
    gap: 4px; z-index: 1;
}
.rr-card-rating-num {
    font-size: 80px; font-weight: 900; line-height: 1;
    letter-spacing: -4px;
    color: rgba(0,0,0,0.22);
}
.rr-card-rating-lbl {
    font-size: 13px; font-weight: 700;
    color: rgba(0,0,0,0.45); letter-spacing: -0.2px;
}
.rr-card-rating-range {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; color: rgba(0,0,0,0.33);
}
.rr-card-body {
    padding: 20px 22px 16px; flex: 1;
}
.rr-card-name {
    font-size: 22px; font-weight: 700; color: var(--text-1);
    margin-bottom: 10px; line-height: 1.3;
    overflow: hidden; display: -webkit-box;
    -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.rr-card-desc {
    font-size: 15px; color: var(--text-2); line-height: 1.6;
    overflow: hidden; display: -webkit-box;
    -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    margin-bottom: 14px; min-height: 3.2em;
}
.rr-card-isin {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px; color: var(--text-3); margin-bottom: 16px;
}
.rr-card-metrics {
    display: flex; border-top: 1px solid var(--border); padding-top: 14px;
    margin-bottom: 0;
}
.rr-card-met-item { flex: 1; text-align: center; }
.rr-card-met-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; color: var(--text-3); text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 6px;
}
.rr-card-met-val { font-size: 18px; font-weight: 700; color: var(--text-1); }
.rr-card-met-nil { font-size: 18px; color: var(--text-3); }
.rr-card-ret-pos { font-size: 18px; font-weight: 700; color: #166534; }
.rr-card-ret-neg { font-size: 18px; font-weight: 700; color: #991B1B; }

/* Все кнопки */
.stButton > button {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    color: var(--text-2) !important;
    font-size: 14px !important; font-weight: 600 !important;
    padding: 11px 22px !important; width: 100% !important;
    transition: all 0.14s !important;
    box-shadow: var(--shadow-sm) !important;
}
.stButton > button:hover {
    background: var(--acc-dim) !important;
    border-color: var(--acc-border) !important;
    color: var(--accent) !important;
    box-shadow: var(--shadow-md) !important;
}

[data-testid="stExpander"] {
    background: var(--surface) !important; border: none !important;
    box-shadow: var(--shadow-sm) !important;
    border-radius: 12px !important; overflow: hidden;
}
[data-testid="stExpander"] summary { color: var(--text-1) !important; font-weight: 600 !important; }
[data-testid="stExpander"] summary:hover { color: var(--accent) !important; }

.stDataFrame { border: none !important; border-radius: 10px !important; box-shadow: var(--shadow-sm) !important; }

/* ── Карточка коэффициентов ──────────────────────────────────────── */
.rr-coeff-card {
    background: var(--surface); border-radius: 14px;
    box-shadow: var(--shadow-sm); padding: 20px 22px; height: 100%;
}
.rr-scenario-note {
    font-size: 11px; color: var(--text-3); margin-top: 14px; line-height: 1.5;
    font-style: italic;
}
.rr-coeff-title {
    font-size: 11px; font-weight: 700; color: var(--accent);
    text-transform: uppercase; letter-spacing: 1.4px;
    padding-bottom: 12px; border-bottom: 1px solid var(--border); margin-bottom: 4px;
}
.rr-coeff-item {
    display: flex; justify-content: space-between; align-items: baseline;
    padding: 12px 0; border-bottom: 1px solid var(--border);
}
.rr-coeff-item:last-child { border-bottom: none; }
.rr-coeff-label { font-size: 13px; color: var(--text-2); }
.rr-coeff-value { font-size: 17px; font-weight: 700; color: var(--text-1); font-family: 'JetBrains Mono', monospace; }
.rr-coeff-nil   { font-size: 17px; color: var(--text-3); }
</style>
""", unsafe_allow_html=True)

# ── Справочники ───────────────────────────────────────────────────────────────

# Шкала опасности — согласована с risk_module/core/visualizer.py
_CLR = {
    1: "#22C55E", 2: "#84CC16", 3: "#EAB308",
    4: "#F97316", 5: "#EF4444", 6: "#DC2626", 7: "#991B1B",
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

# size → (num_px, tick_w, tick_gap, tick_base, tick_step)
_RATING_SIZES = {
    "sm": (21, 3, 1, 3, 1.6),
    "md": (32, 4, 2, 4, 2.4),
    "lg": (52, 6, 3, 6, 3.8),
}

# Плейсхолдер изображения — градиент по цвету рейтинга (до загрузки картинок)
_CARD_GRAD = {
    1: "linear-gradient(135deg,#DCFCE7,#A7F3D0)",
    2: "linear-gradient(135deg,#ECFCCB,#BEF264)",
    3: "linear-gradient(135deg,#FEF9C3,#FDE047)",
    4: "linear-gradient(135deg,#FFEDD5,#FDBA74)",
    5: "linear-gradient(135deg,#FEE2E2,#FCA5A5)",
    6: "linear-gradient(135deg,#FECACA,#F87171)",
    7: "linear-gradient(135deg,#F87171,#EF4444)",
}


def _rating_html(rating: int | None, size: str = "sm") -> str:
    """Сигнатурный знак риска: крупная цифра на фоне карточки (контраст
    гарантирован — фон фиксирован) + шкала-эквалайзер под ней, растущая
    к максимуму и подсвеченная до текущего уровня. Единый знак для строки
    списка, итогового рейтинга и карточек компонент."""
    num_px, tick_w, gap, base, step = _RATING_SIZES[size]
    ticks = "".join(
        f'<div class="tick" style="width:{tick_w}px;height:{base + step * (lvl - 1):.1f}px;'
        f'margin-left:{0 if lvl == 1 else gap}px;'
        f'background:{_CLR[lvl] if (rating and lvl <= rating) else "var(--border-2)"}"></div>'
        for lvl in range(1, 8)
    )
    if rating is None:
        num_html = f'<div class="rr-rating-num" style="font-size:{num_px}px;color:var(--text-3)">—</div>'
    else:
        num_html = f'<div class="rr-rating-num" style="font-size:{num_px}px;color:{_CLR[rating]}">{rating}</div>'
    return (
        f'<div class="rr-rating">{num_html}'
        f'<div class="rr-rating-ticks">{ticks}</div></div>'
    )

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


def _nav_returns(nav) -> dict:
    """Доходность на горизонтах 1М / 3М / 1Г (в %, None если данных нет)."""
    import pandas as pd
    if nav is None or nav.empty:
        return {"1М": None, "3М": None, "1Г": None}
    last = float(nav.iloc[-1])
    today = nav.index.max()

    def ret(days):
        cutoff = today - pd.Timedelta(days=days)
        past = nav[nav.index <= cutoff]
        if past.empty:
            return None
        return (last / float(past.iloc[-1]) - 1) * 100

    return {"1М": ret(30), "3М": ret(91), "1Г": ret(365)}


# Заглушки — заменить на реальные данные при подключении источника
_PLACEHOLDER: dict[str, dict] = {
    "RU000A1039N1": {
        "name":        "Т-Капитал Облигации (TBRU)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "RUB",
        "description": (
            "БПИФ с активным управлением, инвестирующий в рублёвые облигации "
            "российских эмитентов. Цель — превзойти индекс RGBITR. "
            "Управляющая компания — Т-Капитал."
        ),
    },
    "RU000A108WX3": {
        "name":        "Т-Капитал Пассивный доход (TPAY)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "RUB",
        "description": (
            "БПИФ, ориентированный на генерацию регулярного дохода через "
            "вложения в облигации и дивидендные бумаги российских эмитентов. "
            "Управляющая компания — Т-Капитал."
        ),
    },
    "RU000A10A1L8": {
        "name":        "Т-Капитал ОФЗ (TOFZ)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "RUB",
        "description": (
            "БПИФ, вкладывающий в облигации федерального займа (ОФЗ). "
            "Минимальный кредитный риск — эмитент Министерство финансов РФ. "
            "Консервативный инструмент для рублёвых накоплений."
        ),
    },
    "RU000A10B0G9": {
        "name":        "Т-Капитал Трендовые акции (TRND)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "RUB",
        "description": (
            "БПИФ с фокусом на акции российских компаний с выраженным "
            "восходящим моментумом. Активное управление на основе "
            "трендовой стратегии. Управляющая компания — Т-Капитал."
        ),
    },
    "RU000A1011U5": {
        "name":        "Т-Капитал – Вечный портфель, рубли (TRUR)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "RUB",
        "description": (
            "БПИФ по стратегии «вечного портфеля»: капитал поровну делится "
            "между акциями, золотом и облигациями (короткими и длинными) "
            "в рублях. Управляющая компания — Т-Капитал."
        ),
    },
    "RU000A1011S9": {
        "name":        "Т-Капитал – Вечный портфель, доллары (TUSD)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "USD",
        "description": (
            "Та же стратегия «вечного портфеля», что и TRUR, но с "
            "долларовыми инструментами. Управляющая компания — Т-Капитал."
        ),
    },
    "RU000A1011T7": {
        "name":        "Т-Капитал – Вечный портфель, евро (TEUR)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "EUR",
        "description": (
            "Та же стратегия «вечного портфеля», что и TRUR, но с "
            "евровыми инструментами. Управляющая компания — Т-Капитал."
        ),
    },
    "RU000A101X50": {
        "name":        "Т-Капитал Золото (TGLD)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "RUB",
        "description": (
            "БПИФ, отслеживающий стоимость золота через обеспеченные "
            "золотом финансовые инструменты. Управляющая компания — Т-Капитал."
        ),
    },
    "RU000A101X76": {
        "name":        "Т-Капитал Индекс МосБиржи (TMOS)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "RUB",
        "description": (
            "БПИФ, реплицирующий индекс МосБиржи — широкий рынок "
            "крупнейших российских компаний. Управляющая компания — Т-Капитал."
        ),
    },
    "RU000A107597": {
        "name":        "Т-Капитал Локальные валютные облигации (TLCB)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "RUB",
        "description": (
            "БПИФ, инвестирующий в локальные валютные (замещающие) "
            "облигации российских эмитентов. Управляющая компания — Т-Капитал."
        ),
    },
    "RU000A106DL2": {
        "name":        "Т-Капитал Денежный рынок (TMON)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "RUB",
        "description": (
            "БПИФ денежного рынка: краткосрочные сделки обратного репо, "
            "минимальный риск и волатильность. Управляющая компания — Т-Капитал."
        ),
    },
    "RU000A103TD2": {
        "name":        "Т-Капитал Облигации Е (TBEU)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "EUR",
        "description": (
            "БПИФ, инвестирующий в валютные облигации, номинированные в евро. "
            "Управляющая компания — Т-Капитал."
        ),
    },
    "RU000A107563": {
        "name":        "Т-Капитал Дивидендные акции (TDIV)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "RUB",
        "description": (
            "БПИФ из российских акций с высокой дивидендной доходностью. "
            "Управляющая компания — Т-Капитал."
        ),
    },
    "RU000A108BL2": {
        "name":        "Т-Капитал Акции роста (TITR)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "RUB",
        "description": (
            "БПИФ из российских акций с потенциалом роста выше рынка. "
            "Управляющая компания — Т-Капитал."
        ),
    },
    "RU000A10FLY4": {
        "name":        "Т-Капитал Накопительный (TSAV)",
        "issuer":      "Т-Капитал",
        "type":        "БПИФ",
        "currency":    "RUB",
        "description": (
            "БПИФ консервативного накопления — краткосрочные рублёвые "
            "инструменты денежного рынка. Управляющая компания — Т-Капитал."
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

    # T-Bank API — для фондов, которых нет на MOEX
    try:
        from risk_module.data.tbank import find_instrument
        inst = find_instrument(isin)
        if inst and inst.get("name"):
            p = _PLACEHOLDER.get(isin, {})
            return {
                "name":        inst["name"],
                "issuer":      inst.get("ticker", ""),
                "maturity":    p.get("maturity"),
                "currency":    "RUB",
                "coupon":      None,
                "type":        "БПИФ",
                "description": p.get("description", ""),
            }
    except Exception:
        pass

    # Заглушка — в последнюю очередь берём хотя бы имя/тикер из каталога
    p   = _PLACEHOLDER.get(isin, {})
    cat = _FUND_CATALOG.get(isin, {})
    return {
        "name":        p.get("name") or cat.get("name") or isin,
        "issuer":      p.get("issuer") or ("Т-Капитал" if cat else ""),
        "maturity":    p.get("maturity"),
        "currency":    p.get("currency", "RUB"),
        "coupon":      p.get("coupon"),
        "type":        p.get("type") or ("БПИФ" if cat else ""),
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
    """Что на сайте = что в data/reference/funds.csv, и только."""
    return sorted(_FUND_CATALOG.keys())


# ── Файловый кэш рейтингов ────────────────────────────────────────────────────

CACHE_FILE = DATA_DIR / "ratings_cache.json"


def _load_ratings_cache() -> dict | None:
    import json
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_ratings_cache(cache: dict) -> None:
    import json
    CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _result_from_cache(entry: dict):
    """Минимальный объект результата из записи кэша — для list view."""
    from types import SimpleNamespace
    fr = entry.get("final_rating")
    if not fr:
        return None
    comps = [
        SimpleNamespace(component=k, rating=v, meta={}, loss_pct=None)
        for k, v in (entry.get("components") or {}).items()
    ]
    return SimpleNamespace(final_rating=fr, components=comps)


def _recompute_and_save(isins: list) -> dict:
    """Параллельно пересчитывает все рейтинги, сохраняет в JSON и возвращает кэш."""
    from datetime import datetime

    def _one(isin):
        entry = {"meta": {}, "final_rating": None, "components": {}, "nav_returns": {}}
        try:
            result, portfolio = _compute(isin)
            entry["final_rating"] = result.final_rating
            entry["components"] = {
                c.component: c.rating for c in result.components
                if c.meta.get("status") not in (
                    "no_holdings", "no_ratings_found", "no_durations_found")
            }
            entry["nav_returns"] = _nav_returns(portfolio.nav_series)
        except Exception:
            pass
        try:
            m = _fund_meta(isin)
            entry["meta"] = {k: m.get(k, "") for k in ("name", "type", "description", "issuer")}
        except Exception:
            pass
        return isin, entry

    data = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for isin, entry in ex.map(_one, isins):
            data[isin] = entry

    cache = {"computed_at": datetime.now().strftime("%d.%m.%Y %H:%M"), "data": data}
    _save_ratings_cache(cache)
    return cache


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
      <div class="rr-brand-sub">Кроко Рейтинг</div>
    </div>
  </div>
  <div class="rr-header-tag">Аналитика рисков · Внутренняя платформа</div>
</div>
<div class="rr-body">
""", unsafe_allow_html=True)


# ── Обзор книги рисков ───────────────────────────────────────────────────────

def _hero(dist: dict[int, int], total: int) -> None:
    """Открывает страницу тезисом: как выглядит риск всей книги прямо
    сейчас, а не абстрактным объяснением шкалы. Легенда шкалы — под ней,
    как справочный ключ к тем же цветам."""
    rated = sum(dist.values())
    segs, ticks = [], []
    for r in range(1, 8):
        n = dist.get(r, 0)
        if n == 0:
            segs.append(f'<div class="rr-dist-seg empty" style="flex:0.4"></div>')
        else:
            pct = n / rated if rated else 0
            label = str(n) if pct > 0.06 else ""
            segs.append(
                f'<div class="rr-dist-seg" style="flex:{max(pct, 0.02):.4f};background:{_CLR[r]}" '
                f'title="Уровень {r}: {n}">{label}</div>'
            )
        ticks.append(f'<div class="rr-dist-tick">{r}</div>')

    legend_items = "".join(f"""
    <div class="rr-legend-item">
        <div class="rr-legend-top" style="background:{_CLR[r]}"></div>
        <div class="rr-legend-num" style="color:{_CLR[r]}">{r}</div>
        <div class="rr-legend-name">{_RISK_LABEL[r]}</div>
        <div class="rr-legend-loss">{_LOSS_RANGE[r]}</div>
    </div>""" for r in range(1, 8))

    st.markdown(f"""
    <div class="rr-hero">
        <div class="rr-hero-top">
            <div class="rr-hero-title">Риск книги сейчас</div>
            <div class="rr-hero-count"><b>{total}</b> инструментов в покрытии
                {f'· <b>{rated}</b> с рейтингом' if rated != total else ''}</div>
        </div>
        <div class="rr-dist">{''.join(segs)}</div>
        <div class="rr-dist-axis">{''.join(ticks)}</div>
        <div class="rr-legend">{legend_items}</div>
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


def _row_html(isin: str, result, meta: dict, nav) -> str:
    fr   = result.final_rating if result else None
    cm   = {c.component: c for c in result.components} if result else {}
    name = meta.get("name") or isin
    typ  = meta.get("type") or ""
    rets = _nav_returns(nav)

    badge = f'<div class="rr-col-rating">{_rating_html(fr, "sm")}</div>'

    type_html = f'<span class="rr-row-type">{typ}</span>' if typ else ""

    def ret_html(pct):
        if pct is None:
            return '<span class="rr-ret-nil">—</span>'
        cls = "rr-ret-pos" if pct >= 0 else "rr-ret-neg"
        arrow = "▲" if pct >= 0 else "▼"
        sign = "+" if pct >= 0 else ""
        return f'<span class="{cls}"><span class="rr-ret-arrow">{arrow}</span>{sign}{pct:.1f}%</span>'

    def mini(comp):
        r = cm.get(comp)
        if r is None:
            return '<div class="rr-mini-dash">—</div>'
        if r.meta.get("status") in ("no_holdings", "no_ratings_found", "no_durations_found"):
            return '<div class="rr-mini-dash">—</div>'
        c = _CLR.get(r.rating, "#94A3B8")
        return f'<div class="rr-mini-badge" style="background:{c}">{r.rating}</div>'

    def risk_col(label, comp):
        return (f'<div class="rr-col-risk" style="display:flex;flex-direction:column;'
                f'align-items:center;gap:2px">'
                f'<div class="rr-mini-label">{label}</div>{mini(comp)}</div>')

    def ret_col(label, key):
        return (f'<div class="rr-col-ret" style="display:flex;flex-direction:column;'
                f'align-items:flex-end;gap:2px">'
                f'<div class="rr-mini-label">{label}</div>{ret_html(rets[key])}</div>')

    desc = meta.get("description") or meta.get("issuer") or ""
    desc_html = f'<div class="rr-row-desc">{desc}</div>' if desc else ""

    return f"""<div class="rr-row">
      {badge}
      <div class="rr-col-name">
        <span class="rr-row-name" title="{name}">{name}</span>
        {desc_html}
        <div class="rr-row-sub"><span class="rr-row-isin">{isin}</span>{type_html}</div>
      </div>
      <div class="rr-col-sep"></div>
      {ret_col("1М", "1М")}
      {ret_col("3М", "3М")}
      {ret_col("1Г", "1Г")}
      <div class="rr-col-sep"></div>
      {risk_col("VaR", "VaR")}
      {risk_col("Дюр.", "InterestRateRisk")}
      {risk_col("Кред.", "CreditRisk")}
    </div>"""


def _card_html(isin: str, result, meta: dict, nav, rets: dict | None = None) -> str:
    fr   = result.final_rating if result else None
    cm   = {c.component: c for c in result.components} if result else {}
    name = meta.get("name") or isin
    typ  = meta.get("type") or "Инструмент"
    rets = rets if rets is not None else _nav_returns(nav)

    grad       = _CARD_GRAD.get(fr, "linear-gradient(135deg,#F1F5F9,#E2E8F0)")
    rating_num = str(fr) if fr else "—"
    risk_lbl   = _RISK_LABEL.get(fr, "") if fr else ""
    loss_rng   = _LOSS_RANGE.get(fr, "") if fr else ""

    def ret_html(pct):
        if pct is None:
            return '<span class="rr-card-met-nil">—</span>'
        cls  = "rr-card-ret-pos" if pct >= 0 else "rr-card-ret-neg"
        sign = "+" if pct >= 0 else ""
        return f'<span class="{cls}">{sign}{pct:.1f}%</span>'

    def comp_val(comp_name):
        r = cm.get(comp_name)
        if r is None or r.meta.get("status") in (
                "no_holdings", "no_ratings_found", "no_durations_found"):
            return '<span class="rr-card-met-nil">—</span>'
        c = _CLR.get(r.rating, "#94A3B8")
        return f'<span class="rr-card-met-val" style="color:{c}">{r.rating}</span>'

    desc = meta.get("description") or meta.get("issuer") or ""
    desc_html = f'<div class="rr-card-desc">{desc}</div>'

    return f"""<div class="rr-card">
  <div class="rr-card-img" style="background:{grad}">
    <div class="rr-card-tag">{typ}</div>
    <div class="rr-card-rating-center">
      <div class="rr-card-rating-num">{rating_num}</div>
      <div class="rr-card-rating-lbl">{risk_lbl}</div>
      <div class="rr-card-rating-range">{loss_rng}</div>
    </div>
  </div>
  <div class="rr-card-body">
    <div class="rr-card-name" title="{name}">{name}</div>
    {desc_html}
    <div class="rr-card-isin">{isin}</div>
    <div class="rr-card-metrics">
      <div class="rr-card-met-item">
        <div class="rr-card-met-label">1М доходн.</div>
        {ret_html(rets.get("1М"))}
      </div>
      <div class="rr-card-met-item">
        <div class="rr-card-met-label">VaR</div>
        {comp_val("VaR")}
      </div>
      <div class="rr-card-met-item">
        <div class="rr-card-met-label">Кредит</div>
        {comp_val("CreditRisk")}
      </div>
    </div>
  </div>
</div>"""


# ── Список ────────────────────────────────────────────────────────────────────

def show_list():
    isins = _available_isins()
    if not isins:
        st.warning("Нет файлов в data/products/")
        return

    # Загружаем кэш из файла; пересчитываем если кэша нет или нажата кнопка
    cache = _load_ratings_cache()
    if not cache or st.session_state.pop("_recalc", False):
        with st.spinner("Считаем рейтинги… это займёт ~30 сек"):
            cache = _recompute_and_save(isins)

    cached_data  = cache.get("data", {})
    computed_at  = cache.get("computed_at", "")
    rated        = sum(1 for e in cached_data.values() if e.get("final_rating"))

    count_txt = (
        f'<b>{len(isins)}</b> инструментов в покрытии'
        + (f' · <b>{rated}</b> с рейтингом' if rated != len(isins) else '')
    )
    scale_cells = "".join(
        f'<div class="rr-scale-cell" style="border-top-color:{_CLR[r]}">'
        f'<div class="rr-scale-n" style="color:{_CLR[r]}">{r}</div>'
        f'<div class="rr-scale-lbl">{_RISK_LABEL[r]}</div>'
        f'<div class="rr-scale-loss">{_LOSS_RANGE[r]}</div>'
        f'</div>'
        for r in range(1, 8)
    )
    st.markdown(f"""
    <div class="rr-topbar">
      <div class="rr-count">{count_txt}</div>
      <div class="rr-scale-strip">{scale_cells}</div>
      <div class="rr-topbar-divider"></div>
      <div class="rr-topbar-about">
        <div class="rr-topbar-desc">
          Кроко Рейтинг — внутренняя шкала риска от 1 до 7, оценивающая
          ожидаемые потери инструмента в стрессовом сценарии. Учитывает
          исторический VaR, стресс-тест, кредитный риск эмитента,
          дюрацию и качество выпуска.
        </div>
        <div class="rr-topbar-disclaimer">
          Не является индивидуальной инвестиционной рекомендацией.
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Кнопка пересчёта + метка даты
    btn_col, ts_col = st.columns([1, 4])
    with btn_col:
        if st.button("↻  Пересчитать рейтинги", key="_btn_recalc"):
            st.session_state["_recalc"] = True
            st.rerun()
    with ts_col:
        if computed_at:
            st.markdown(
                f'<div style="font-size:12px;color:var(--text-3);padding:10px 0 0 4px">'
                f'Последний расчёт: {computed_at}</div>',
                unsafe_allow_html=True,
            )

    # Фильтры: поиск + рейтинг
    col_s, col_f = st.columns([3, 2])
    with col_s:
        search = st.text_input("search", placeholder="🔍  Поиск по ISIN или названию...",
                               label_visibility="collapsed")
    with col_f:
        rating_filter = st.multiselect(
            "Рейтинг",
            options=list(range(1, 8)),
            format_func=lambda r: f"{r} — {_RISK_LABEL[r]}  ·  {_LOSS_RANGE[r]}",
            placeholder="Фильтр по рейтингу...",
            label_visibility="collapsed",
        )

    # Применяем фильтры
    selected_ratings = set(rating_filter or [])
    filtered = []
    for isin in isins:
        entry = cached_data.get(isin, {})
        name  = entry.get("meta", {}).get("name") or ""
        if search.strip() and search.strip().upper() not in (isin + name).upper():
            continue
        if selected_ratings:
            if entry.get("final_rating") not in selected_ratings:
                continue
        filtered.append(isin)

    if not filtered:
        st.markdown('<div style="color:#7DA893;padding:28px 0;font-size:16px">Ничего не найдено</div>',
                    unsafe_allow_html=True)
        return

    # Грид карточек — 3 колонки
    cols = st.columns(3, gap="large")
    for idx, isin in enumerate(filtered):
        entry  = cached_data.get(isin, {})
        result = _result_from_cache(entry)
        meta   = entry.get("meta", {})
        rets   = entry.get("nav_returns") or {}
        with cols[idx % 3]:
            with st.container():
                st.markdown(
                    _card_html(isin, result, meta, None, rets=rets),
                    unsafe_allow_html=True,
                )
                if st.button(" ", key=f"go_{isin}"):
                    st.session_state.selected = isin
                    st.rerun()

    # JS: клик по карточке → click() на скрытую кнопку Streamlit
    components.html("""
<script>
(function() {
  function wire() {
    var doc = window.parent.document;
    doc.querySelectorAll('.rr-card:not([data-wired])').forEach(function(card) {
      card.dataset.wired = '1';
      // Ближайший stVerticalBlock (создан st.container())
      var vblock = card.closest('[data-testid="stVerticalBlock"]');
      if (!vblock) return;
      var btn = vblock.querySelector('[data-testid="stButton"] button');
      if (!btn) return;
      card.addEventListener('mouseenter', function() { card.classList.add('rr-card-hovered'); });
      card.addEventListener('mouseleave', function() { card.classList.remove('rr-card-hovered'); });
      card.addEventListener('click', function() { btn.click(); });
    });
  }
  wire();
  new MutationObserver(wire).observe(
    window.parent.document.body, {childList: true, subtree: true}
  );
})();
</script>
""", height=0)


# ── QuantStats tearsheet ─────────────────────────────────────────────────────

def _qs_report_path(isin: str, nav: "pd.Series") -> "pathlib.Path | None":
    """Generate (or reuse cached) quantstats tearsheet for a NAV series."""
    import time
    out_dir = DATA_DIR / "qs_reports"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{isin}.html"
    # Reuse if file is fresh (<24 h)
    if out_path.exists() and (time.time() - out_path.stat().st_mtime) < 86_400:
        return out_path
    if nav is None or nav.empty or len(nav) < 30:
        return None
    try:
        import quantstats as qs
        returns = nav.pct_change().dropna()
        qs.reports.html(
            returns,
            output=str(out_path),
            title=isin,
            rf=0.16 / 252,
            periods_per_year=252,
            figfmt="svg",
        )
        return out_path
    except Exception:
        return None


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
        {_rating_html(fr, "lg")}
        <div>
            <div class="rr-final-label">Кроко рейтинг</div>
            <div class="rr-final-name" style="color:{fc}">{_RISK_LABEL.get(fr,'')}</div>
            <div class="rr-final-hint">Ожидаемые потери в стрессовом сценарии: {_LOSS_RANGE.get(fr,'—')}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Сценарный прогноз ─────────────────────────────────────────────────────
    _sc_nav = portfolio.nav_series
    if _sc_nav is not None and not _sc_nav.empty and len(_sc_nav) >= 30:
        import plotly.graph_objects as go
        import numpy as np

        _rets   = _sc_nav.pct_change().dropna()
        _mu     = float(_rets.mean() * 252)
        _sigma  = float(_rets.std() * (252 ** 0.5))
        _last_p = float(_sc_nav.iloc[-1])
        _last_d = _sc_nav.index.max()

        # Последние 2 года истории
        _nav_trim = _sc_nav[_sc_nav.index >= _last_d - pd.DateOffset(years=2)]

        # 252 торговых дня вперёд
        _fd  = pd.bdate_range(_last_d, periods=253)[1:]
        _t   = np.arange(1, 253) / 252
        _bear = _last_p * (1 + (_mu - 1.5 * _sigma) * _t)
        _base = _last_p * (1 + _mu * _t)
        _bull = _last_p * (1 + (_mu + 1.5 * _sigma) * _t)

        st.markdown('<div class="rr-section">Прогноз на 12 месяцев</div>',
                    unsafe_allow_html=True)
        _sc_chart, _sc_desc = st.columns([3, 1], gap="large")

        with _sc_chart:
            _fig = go.Figure()

            # Исторический NAV
            _fig.add_trace(go.Scatter(
                x=_nav_trim.index, y=_nav_trim.values,
                mode="lines", name="История",
                line=dict(color="#0A7A54", width=2.5),
            ))

            # Диапазон между медвежьим и бычьим
            _fig.add_trace(go.Scatter(
                x=list(_fd) + list(_fd[::-1]),
                y=list(_bull) + list(_bear[::-1]),
                fill="toself", fillcolor="rgba(234,179,8,0.10)",
                line=dict(color="rgba(0,0,0,0)"),
                showlegend=False, hoverinfo="skip",
            ))

            # Линии сценариев
            for _name, _vals, _clr, _dash in [
                ("Оптимистичный", _bull, "#22C55E", "dot"),
                ("Базовый",       _base, "#6B7280", "dash"),
                ("Медвежий",      _bear, "#EF4444", "dot"),
            ]:
                _fig.add_trace(go.Scatter(
                    x=_fd, y=_vals, mode="lines", name=_name,
                    line=dict(color=_clr, width=1.8, dash=_dash),
                ))

            # Разделитель «сегодня»
            _fig.add_vline(
                x=str(_last_d.date()),
                line=dict(color="#CCCCCC", width=1, dash="dash"),
            )

            _fig.update_layout(
                paper_bgcolor="#EBEBED", plot_bgcolor="#FFFFFF",
                height=320, margin=dict(l=10, r=10, t=10, b=10),
                xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#AAAAAA")),
                yaxis=dict(gridcolor="#F0F0F2", tickfont=dict(size=10, color="#AAAAAA")),
                legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
                            font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
                hovermode="x unified",
            )
            st.plotly_chart(_fig, use_container_width=True)

        with _sc_desc:
            def _sc_row(label, ret, clr):
                sign = "+" if ret >= 0 else ""
                return (
                    f'<div class="rr-coeff-item">'
                    f'<span class="rr-coeff-label">{label}</span>'
                    f'<span class="rr-coeff-value" style="color:{clr}">'
                    f'{sign}{ret:.1f}%</span></div>'
                )
            _bear_ret = (_mu - 1.5 * _sigma) * 100
            _base_ret = _mu * 100
            _bull_ret = (_mu + 1.5 * _sigma) * 100
            st.markdown(f"""
            <div class="rr-coeff-card">
              <div class="rr-coeff-title">Прогноз, 12 мес.</div>
              {_sc_row("Оптимистичный", _bull_ret, "#22C55E")}
              {_sc_row("Базовый",       _base_ret, "#6B7280")}
              {_sc_row("Медвежий",      _bear_ret, "#EF4444")}
              <div class="rr-scenario-note">
                Диапазоны рассчитаны из исторической волатильности (±1.5σ).<br>
                Не является инвестиционной рекомендацией.
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
            {_rating_html(comp.rating, "md")}
            <div class="rr-comp-sub">{sub}</div>
        </div>"""
    cards += "</div>"
    st.markdown(cards, unsafe_allow_html=True)

    # Диаграмма — уже тёмная в своей палитре (risk_module/core/visualizer.py),
    # согласованной с этой страницей; только подгоняем размеры под колонку.
    from risk_module.core.visualizer import plot_risk_result
    fig = plot_risk_result(result)
    fig.update_layout(width=None, height=360, margin=dict(l=20, r=20, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # ── QuantStats tearsheet ───────────────────────────────────────────────────
    nav = portfolio.nav_series
    qs_path = _qs_report_path(isin, nav)
    if qs_path is not None:
        st.markdown(
            '<div class="rr-section" style="margin-top:8px">Аналитика фонда (QuantStats)</div>',
            unsafe_allow_html=True,
        )
        st.iframe(qs_path, height=2800)
    else:
        st.markdown(
            '<div style="color:var(--text-3);font-size:13px;margin-top:16px">'
            'История цен недостаточна для построения отчёта (&lt; 30 торговых дней).</div>',
            unsafe_allow_html=True,
        )


# ── Router ────────────────────────────────────────────────────────────────────

if st.session_state.selected is None:
    show_list()
else:
    show_detail(st.session_state.selected)

st.markdown("</div>", unsafe_allow_html=True)
