import pathlib

import streamlit as st

BASE_DIR = pathlib.Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

BRAND_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 40px 60px !important; max-width: 100% !important; }
section[data-testid="stSidebar"] { display: none; }

.rr-header {
    background: #FFFFFF;
    border-bottom: 1px solid #D9EDDF;
    padding: 16px 40px;
    margin: 0 -40px 4px -40px;
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

.rr-navrow { display: flex; align-items: center; gap: 6px; padding: 18px 0 22px; }
.rr-nav-pill {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 7px 18px; border-radius: 20px;
    font-size: 13px; font-weight: 600;
    white-space: nowrap;
}
.rr-nav-pill-active { background: #0C7A56; color: #FFFFFF; }
.rr-navrow [data-testid="stPageLink"] a {
    display: inline-flex !important; align-items: center; gap: 6px;
    padding: 7px 18px !important;
    border-radius: 20px !important;
    border: 1px solid #D9EDDF !important;
    background: #FFFFFF !important;
    font-size: 13px !important; font-weight: 600 !important;
    color: #537165 !important;
    text-decoration: none !important;
    width: fit-content !important;
}
.rr-navrow [data-testid="stPageLink"] a:hover { border-color: #0C7A56 !important; color: #0C7A56 !important; }

.stButton > button {
    background: #F4FAF7 !important;
    border: 1px solid #C0DCCB !important;
    border-radius: 8px !important;
    color: #0C7A56 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 5px 16px !important;
    transition: all 0.12s !important;
}
.stButton > button:hover {
    background: #0C7A56 !important;
    border-color: #0C7A56 !important;
    color: #FFFFFF !important;
}
</style>
"""

_NAV_TABS = [
    ("home", "🏠", "Все инструменты", "app.py"),
    ("risk", "📊", "Риск-рейтинг", "pages/1_Risk_Rating.py"),
    ("kelly", "🎯", "Критерий Келли", "pages/2_Kelly_Criterion.py"),
]


def render_header(tag: str) -> None:
    """Injects brand CSS and renders the shared header bar."""
    st.markdown(BRAND_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="rr-header">
          <div class="rr-brand">
            <div class="rr-logo">🐊</div>
            <div>
              <div class="rr-brand-name">Kroko Capital</div>
              <div class="rr-brand-sub">Финансовые калькуляторы</div>
            </div>
          </div>
          <div class="rr-header-tag">{tag}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_nav(active: str) -> None:
    st.markdown('<div class="rr-navrow">', unsafe_allow_html=True)
    cols = st.columns([1, 1, 1, 6], gap="small")
    for col, (key, icon, label, target) in zip(cols, _NAV_TABS):
        with col:
            if key == active:
                st.markdown(
                    f'<div class="rr-nav-pill rr-nav-pill-active">{icon} {label}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.page_link(target, label=label, icon=icon)
    st.markdown("</div>", unsafe_allow_html=True)
