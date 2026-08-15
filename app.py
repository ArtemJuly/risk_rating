import streamlit as st

from site_common import render_header, render_nav

st.set_page_config(
    page_title="Kroko Capital · Калькуляторы",
    page_icon="🐊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

render_header("Финансовые калькуляторы")
render_nav("home")

st.markdown(
    """
    <style>
    .product-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 18px;
        margin-top: 4px;
        max-width: 360px;
    }
    .product-card {
        background: #FFFFFF;
        border: 1px solid #D9EDDF;
        border-radius: 14px;
        padding: 26px 26px 22px;
        box-shadow: 0 1px 4px rgba(12, 122, 86, 0.06);
    }
    .product-icon {
        width: 48px; height: 48px;
        border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        font-size: 24px; margin-bottom: 16px;
        background: linear-gradient(135deg, #0C7A56, #14A072);
    }
    .product-title { font-size: 17px; font-weight: 800; color: #1A2B23; margin-bottom: 6px; }
    .product-desc  { font-size: 13px; color: #537165; line-height: 1.6; margin-bottom: 4px; min-height: 62px; }
    </style>

    <div class="product-grid">
      <div class="product-card">
        <div class="product-icon">🎯</div>
        <div class="product-title">Критерий Келли</div>
        <div class="product-desc">
            Оптимальная доля капитала на сделку — по вероятности выигрыша
            и соотношению средней прибыли к среднему убытку.
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
col1, _ = st.columns([1, 2], gap="medium")
with col1:
    st.page_link("pages/2_Kelly_Criterion.py", label="Открыть критерий Келли →", icon="🎯", use_container_width=True)
