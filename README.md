# Risk Module

Модуль для риск-рейтингования инвестиционных продуктов.  
Содержит реализацию как простых стресс-сценариев, так и модельных (на основе **LightAutoML**).

---

## Структура проекта

risk_module/
│
├── core/
│ └── engine.py # Оркестратор, общий интерфейс RiskEngine
│
├── quantitative/
│ └── stress_test.py # Реализация StressTest и StressTestLAMA
│
├── qualitative/ # (заготовка) Качественные риски
│
├── notebooks/ # Jupyter ноутбуки с расчётами
└── tests/ # Тесты


## Установка

### 1. Клонировать репозиторий


### 2. Запустить код в терминале

python3 -m venv .venv
source .venv/bin/activate


pip install --upgrade pip
pip install -e .
pip install pandas numpy scikit-learn openpyxl lightautoml
pip install gensim nltk transformers


## Пример использования описан в notebooks/test.ipynb