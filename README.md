<h1 align="center">Анализ пролонгаций 2023</h1>

<p align="center">
  <b>Data Analyst проект по оценке эффективности пролонгации договоров</b>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.13-blue">
  <img alt="Pandas" src="https://img.shields.io/badge/Pandas-analysis-150458">
  <img alt="Jupyter" src="https://img.shields.io/badge/Jupyter-Notebook-f37626">
  <img alt="Excel" src="https://img.shields.io/badge/Report-Excel-217346">
</p>

<p align="center">
  <b>K1:</b> 0.4743 &nbsp; | &nbsp; <b>K2:</b> 0.0642 &nbsp; | &nbsp; <b>Период:</b> 2023
</p>

Краткий аналитический проект по расчёту коэффициентов пролонгации договоров для аккаунт-менеджеров отдела сопровождения клиентов.

## Что сделано

- рассчитаны коэффициенты пролонгации в первый и второй месяц;
- подготовлена детализация по месяцам, менеджерам и отделу в целом;
- обработаны специальные значения `стоп`, `end`, `в ноль` и пустые месяцы;
- сформирован Excel-отчёт для руководителя.

## Структура проекта

```text
.
├── analys_prolongation.ipynb          # основной ноутбук с запуском расчёта
├── data/
│   ├── financial_data.csv             # отгрузки по проектам
│   └── prolongations.csv              # даты завершения и ответственные менеджеры
├── reports/
│   └── report_prolongation_2023.xlsx  # итоговый отчёт
├── src/
│   ├── data_preparation.py            # загрузка и подготовка данных
│   ├── prolongation_calculator.py     # логика расчёта коэффициентов
│   └── excel_report.py                # генерация Excel-отчёта
└── requirements.txt
```

## Результат

Итоговые коэффициенты по отделу за 2023 год:

| Метрика | Коэффициент |
|---|---:|
| Пролонгация в первый месяц | 0.4743 |
| Пролонгация во второй месяц | 0.0642 |

Excel-отчёт содержит обязательные листы по шаблону и дополнительные управленческие листы: `Итоги`, `Рейтинг менеджеров`, `Исключенные проекты`.

## Запуск

```bash
pip install -r requirements.txt
jupyter notebook analys_prolongation.ipynb
```

После запуска ноутбука отчёт сохраняется в:

```text
reports/report_prolongation_2023.xlsx
```

## Примечание

Поле `AM` из `prolongations.csv` используется как основной источник менеджера, так как по условию задания оно первично относительно `Account` из `financial_data.csv`.

---

<p align="center">
  <b>Итог:</b> воспроизводимый расчёт, готовый Excel-отчёт и понятная структура проекта для проверки.
</p>

<p align="center">
  <sub>Python · Pandas · Jupyter Notebook · OpenPyXL · Data Analytics</sub>
</p>
