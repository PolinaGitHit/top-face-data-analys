from pathlib import Path

import numpy as np
import pandas as pd


RU_MONTHS = {
    "январь": 1,
    "февраль": 2,
    "март": 3,
    "апрель": 4,
    "май": 5,
    "июнь": 6,
    "июль": 7,
    "август": 8,
    "сентябрь": 9,
    "октябрь": 10,
    "ноябрь": 11,
    "декабрь": 12,
}

RU_MONTH_LABEL = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}

META_COLS = {"id", "Причина дубля", "Account"}


def ru_month_year_to_period(text) -> pd.Period:
    if pd.isna(text):
        return pd.NaT
    s = str(text).strip().lower().replace("ё", "е")
    parts = s.split()
    if len(parts) != 2:
        raise ValueError(f"Ожидалось 'месяц год', получено: {text!r}")
    month_word, year_word = parts
    if month_word not in RU_MONTHS:
        raise ValueError(f"Неизвестный месяц: {month_word!r} в {text!r}")
    return pd.Period(year=int(year_word), month=RU_MONTHS[month_word], freq="M")


def is_month_column(name: str) -> bool:
    if name in META_COLS:
        return False
    parts = str(name).strip().split()
    month_ok = parts[0].strip().lower().replace("ё", "е") in RU_MONTHS
    year_ok = len(parts) == 2 and parts[1].isdigit()
    return month_ok and year_ok


def financial_col_to_period(col_name: str) -> pd.Period:
    parts = str(col_name).strip().split()
    month_word = parts[0].lower().replace("ё", "е")
    year_word = parts[1]
    return pd.Period(year=int(year_word), month=RU_MONTHS[month_word], freq="M")


def parse_money_cell(x):
    if pd.isna(x):
        return np.nan
    if isinstance(x, (int, float, np.integer, np.floating)):
        return float(x)
    s = str(x).strip()
    if s == "":
        return np.nan
    low = s.lower()
    if low in ("стоп", "end", "в ноль"):
        return low
    s_num = s.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s_num)
    except ValueError:
        return x


def load_data(root: Path):
    data_dir = root / "data"
    prolongations = pd.read_csv(data_dir / "prolongations.csv", encoding="utf-8", sep=",")
    financial_data = pd.read_csv(data_dir / "financial_data.csv", encoding="utf-8", sep=",")

    financial_data.columns = financial_data.columns.str.strip()
    prolongations["id"] = prolongations["id"].astype(int)
    financial_data["id"] = financial_data["id"].astype(int)
    return prolongations, financial_data


def prepare_data(prolongations: pd.DataFrame, financial_data: pd.DataFrame):
    prolongations = prolongations.copy()
    financial_data = financial_data.copy()

    prolongations["month_period"] = prolongations["month"].map(ru_month_year_to_period)
    prolongations["manager"] = prolongations["AM"].astype(str).str.strip()

    month_cols = [c for c in financial_data.columns if is_month_column(c)]
    period_to_col = {financial_col_to_period(c): c for c in month_cols}
    col_to_period = {c: financial_col_to_period(c) for c in month_cols}

    for col in month_cols:
        financial_data[col] = financial_data[col].map(parse_money_cell)

    return prolongations, financial_data, month_cols, period_to_col, col_to_period
