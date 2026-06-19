"""
Расчёт риск-рейтинга для заданного ISIN.

Использование:
    python run.py RU000A1002S8
    python run.py RU000A1002S8 --no-browser
"""

import argparse
import pathlib
import sys
import webbrowser

BASE_DIR = pathlib.Path(__file__).parent
DATA_DIR = BASE_DIR / "data"


def build_engine():
    from risk_module.quantitative.var import VaRComponent
    from risk_module.quantitative.beta_stress import BetaStressComponent
    from risk_module.qualitative.credit_risk.by_rating import CreditRiskComponent
    from risk_module.qualitative.interest_rate_risk.by_duration import InterestRateRiskComponent
    from risk_module.core.engine import RiskEngine

    db_path = str(DATA_DIR / "reference" / "bonds_db.xlsx")

    components = [
        VaRComponent(),
        BetaStressComponent(
            index_file=str(DATA_DIR / "market" / "rgbitr.xlsx"),
            stress_start="2014-07-01",
            stress_end="2014-12-31",
            index_label="RGBITR",
        ),
        CreditRiskComponent(db_path=db_path),
        InterestRateRiskComponent(db_path=db_path),
    ]
    return RiskEngine(components)


def main():
    parser = argparse.ArgumentParser(description="Риск-рейтинг инвестиционного продукта")
    parser.add_argument("isin", help="ISIN фонда, например RU000A1002S8")
    parser.add_argument("--no-browser", action="store_true",
                        help="Не открывать браузер, только сохранить HTML")
    args = parser.parse_args()

    isin = args.isin.strip().upper()

    from risk_module.core.loader import DataLoader
    from risk_module.core.visualizer import plot_risk_result

    print(f"Загружаем данные для {isin}...")
    loader = DataLoader(DATA_DIR)
    portfolio = loader.load(isin)
    print(f"  NAV: {len(portfolio.nav_series)} строк  |  Holdings: {len(portfolio.holdings)} бумаг")

    print("Считаем компоненты риска...")
    engine = build_engine()
    result = engine.calculate(portfolio)

    print()
    print(f"{'─' * 40}")
    for comp in result.components:
        loss_str = f"  (потери: {comp.loss_pct * 100:.1f}%)" if comp.loss_pct else ""
        print(f"  {comp.component:<22} → {comp.rating}{loss_str}")
    print(f"{'─' * 40}")
    print(f"  ИТОГОВЫЙ РЕЙТИНГ         → {result.final_rating}")
    print(f"{'─' * 40}")
    print()

    fig = plot_risk_result(result)

    out_html = BASE_DIR / f"risk_rating_{isin}.html"
    fig.write_html(str(out_html))
    print(f"Сохранено: {out_html}")

    if not args.no_browser:
        webbrowser.open(out_html.as_uri())
        print("Открываем в браузере...")


if __name__ == "__main__":
    main()
