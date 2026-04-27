from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data_preparation import RU_MONTH_LABEL


@dataclass
class ProlongationResult:
    fin_long: pd.DataFrame
    proj: pd.DataFrame
    ship_eff: pd.DataFrame
    exclude_stop_set: set
    exclusion_reasons: dict
    months: list
    managers: list
    dept_rows: list
    mgr_rows: list
    mat_k1: pd.DataFrame
    mat_k2: pd.DataFrame
    year_dept_k1: dict
    year_dept_k2: dict
    df_dept: pd.DataFrame
    df_mgr_year: pd.DataFrame


def period_ru(p: pd.Period) -> str:
    return f"{RU_MONTH_LABEL[p.month]} {p.year}"


def coef(num: float, den: float) -> float:
    if not den or den == 0:
        return np.nan
    x = num / den
    if pd.isna(x) or np.isinf(x):
        return np.nan
    return round(float(x), 4)


def _norm_cell(v):
    if pd.isna(v):
        return "empty", None
    if isinstance(v, str):
        s = v.strip().lower()
        if s == "стоп":
            return "stop", None
        if s == "end":
            return "end", None
        if s == "в ноль":
            return "v_nol", None
        return "bad_string", v
    f = float(v)
    if np.isnan(f):
        return "empty", None
    if f == 0:
        return "zero", None
    return "num", f


def aggregate_one_month(s: pd.Series) -> pd.Series:
    has_stop = False
    has_end = False
    sum_num = 0.0
    has_zero_like_payment = False
    all_observed_parts_zero_like = True

    for v in s:
        kind, payload = _norm_cell(v)
        if kind == "empty":
            # Пустой месяц означает отсутствие отгрузки, а не оплату "в ноль".
            continue
        if kind == "stop":
            has_stop = True
            all_observed_parts_zero_like = False
        elif kind == "end":
            has_end = True
            all_observed_parts_zero_like = False
        elif kind in ("v_nol", "zero"):
            has_zero_like_payment = True
        elif kind == "num":
            sum_num += payload
            all_observed_parts_zero_like = False
        else:
            all_observed_parts_zero_like = False

    if sum_num != 0:
        all_observed_parts_zero_like = False

    return pd.Series(
        {
            "sum_num": sum_num,
            "has_stop": has_stop,
            "has_end": has_end,
            "all_parts_zero_like": has_zero_like_payment and all_observed_parts_zero_like,
        }
    )


def build_financial_long(financial_data: pd.DataFrame, month_cols: list, col_to_period: dict):
    agg_rows = []
    grouped = financial_data.groupby("id", sort=False)

    for col in month_cols:
        p = col_to_period[col]
        for pid, sub in grouped:
            st = aggregate_one_month(sub[col])
            agg_rows.append(
                {
                    "id": pid,
                    "period": p,
                    "sum_num": float(st["sum_num"]),
                    "has_stop": bool(st["has_stop"]),
                    "has_end": bool(st["has_end"]),
                    "all_parts_zero_like": bool(st["all_parts_zero_like"]),
                }
            )

    fin_long = pd.DataFrame(agg_rows)
    return fin_long.groupby(["id", "period"], as_index=False).agg(
        sum_num=("sum_num", "sum"),
        has_stop=("has_stop", "any"),
        has_end=("has_end", "any"),
        all_parts_zero_like=("all_parts_zero_like", "all"),
    )


def build_effective_shipments(fin_long: pd.DataFrame, financial_data: pd.DataFrame, all_periods: list):
    idx_all = pd.Index(sorted(financial_data["id"].unique()))

    pivot_sum = fin_long.pivot(index="id", columns="period", values="sum_num").reindex(idx_all)
    pivot_stop = (
        fin_long.pivot(index="id", columns="period", values="has_stop").reindex(idx_all).fillna(False)
    )
    pivot_end = (
        fin_long.pivot(index="id", columns="period", values="has_end").reindex(idx_all).fillna(False)
    )
    pivot_allzero = (
        fin_long.pivot(index="id", columns="period", values="all_parts_zero_like")
        .reindex(idx_all)
        .fillna(False)
    )

    ship_eff = pd.DataFrame(index=idx_all, columns=all_periods, dtype=float)
    for pid in ship_eff.index:
        for p in all_periods:
            if p not in pivot_stop.columns:
                ship_eff.loc[pid, p] = np.nan
                continue
            if pivot_stop.loc[pid, p] or pivot_end.loc[pid, p]:
                ship_eff.loc[pid, p] = np.nan
                continue
            if not pivot_allzero.loc[pid, p]:
                v = pivot_sum.loc[pid, p]
                ship_eff.loc[pid, p] = float(v) if pd.notna(v) else 0.0
                continue

            chain_p = p - 1
            val = np.nan
            while chain_p in all_periods:
                if pivot_stop.loc[pid, chain_p] or pivot_end.loc[pid, chain_p]:
                    break
                if not pivot_allzero.loc[pid, chain_p]:
                    v = pivot_sum.loc[pid, chain_p]
                    val = float(v) if pd.notna(v) else 0.0
                    break
                chain_p = chain_p - 1
            ship_eff.loc[pid, p] = val

    return ship_eff.sort_index(axis=1), pivot_stop, pivot_end


def build_projects(prolongations: pd.DataFrame, ship_eff: pd.DataFrame, pivot_stop, pivot_end, all_periods):
    proj = prolongations.drop_duplicates(subset=["id"]).set_index("id")

    exclude_stop = []
    exclusion_reasons = {}
    for pid, r in proj.iterrows():
        m_last = r["month_period"]
        if pd.isna(m_last):
            exclude_stop.append(pid)
            exclusion_reasons[pid] = "Не распознан последний месяц реализации"
            continue
        if pid not in ship_eff.index:
            exclude_stop.append(pid)
            exclusion_reasons[pid] = "Нет финансовых данных по проекту"
            continue

        bad = False
        bad_period = None
        for p in all_periods:
            if p > m_last or p not in pivot_stop.columns:
                continue
            if pivot_stop.loc[pid, p] or pivot_end.loc[pid, p]:
                bad = True
                bad_period = p
                break
        if bad:
            exclude_stop.append(pid)
            exclusion_reasons[pid] = f"Есть стоп/end в {period_ru(bad_period)} или ранее"

    exclude_stop_set = set(exclude_stop)
    proj["eligible"] = ~proj.index.isin(exclude_stop_set)

    ship_cols = {f"ship_eff__{p}": ship_eff[p] for p in all_periods if p in ship_eff.columns}
    projects_ready = proj.join(pd.DataFrame(ship_cols))
    return projects_ready, exclude_stop_set, exclusion_reasons


def get_shipment(ship_eff: pd.DataFrame, pid, period: pd.Period) -> float:
    if pid not in ship_eff.index or period not in ship_eff.columns:
        return np.nan
    v = ship_eff.loc[pid, period]
    return float(v) if pd.notna(v) else np.nan


def calculate_prolongation_report(
    prolongations: pd.DataFrame,
    financial_data: pd.DataFrame,
    month_cols: list,
    col_to_period: dict,
    year: int = 2023,
) -> ProlongationResult:
    all_periods = sorted(col_to_period[c] for c in month_cols)
    fin_long = build_financial_long(financial_data, month_cols, col_to_period)
    ship_eff, pivot_stop, pivot_end = build_effective_shipments(fin_long, financial_data, all_periods)
    proj, exclude_stop_set, exclusion_reasons = build_projects(
        prolongations, ship_eff, pivot_stop, pivot_end, all_periods
    )

    months = list(pd.period_range(f"{year}-01", f"{year}-12", freq="M"))
    store = defaultdict(
        lambda: defaultdict(
            lambda: {
                "k1": {"num": 0.0, "den": 0.0},
                "k2": {"num": 0.0, "den": 0.0},
            }
        )
    )

    def ship_val(pid, p: pd.Period) -> float:
        return get_shipment(ship_eff, pid, p)

    def has_shipment(pid, p: pd.Period) -> bool:
        v = ship_val(pid, p)
        return pd.notna(v) and v > 0

    def no_shipment_or_zero(pid, p: pd.Period) -> bool:
        v = ship_val(pid, p)
        return pd.isna(v) or v <= 0

    def add_k(mgr, T, which, num_d, den_d):
        store[mgr][T][which]["num"] += num_d
        store[mgr][T][which]["den"] += den_d

    for T in months:
        m1 = T - 1
        m2 = T - 2

        sub1 = proj.loc[proj["eligible"] & (proj["month_period"] == m1)]
        for pid, row in sub1.iterrows():
            mgr = row["manager"]
            base = ship_val(pid, m1)
            if pd.isna(base):
                continue
            num = ship_val(pid, T) if has_shipment(pid, T) else 0.0
            add_k(None, T, "k1", num, base)
            add_k(mgr, T, "k1", num, base)

        sub2 = proj.loc[proj["eligible"] & (proj["month_period"] == m2)]
        for pid, row in sub2.iterrows():
            if not no_shipment_or_zero(pid, m1):
                continue
            mgr = row["manager"]
            base = ship_val(pid, m2)
            if pd.isna(base):
                continue
            num = ship_val(pid, T) if has_shipment(pid, T) else 0.0
            add_k(None, T, "k2", num, base)
            add_k(mgr, T, "k2", num, base)

    col_tuples = [
        ("Пролонгации в первый месяц", "к пролонгации"),
        ("Пролонгации в первый месяц", "пролонгировано"),
        ("Пролонгации в первый месяц", "Коэффициент"),
        ("Пролонгации через месяц", "к пролонгации"),
        ("Пролонгации через месяц", "пролонгировано"),
        ("Пролонгации через месяц", "Коэффициент"),
    ]

    k1d = [store[None][T]["k1"]["den"] for T in months]
    k1n = [store[None][T]["k1"]["num"] for T in months]
    k2d = [store[None][T]["k2"]["den"] for T in months]
    k2n = [store[None][T]["k2"]["num"] for T in months]

    df_dept = pd.DataFrame(
        {
            ("Месяц", ""): [period_ru(T) for T in months],
            col_tuples[0]: k1d,
            col_tuples[1]: k1n,
            col_tuples[2]: [coef(n, d) for n, d in zip(k1n, k1d)],
            col_tuples[3]: k2d,
            col_tuples[4]: k2n,
            col_tuples[5]: [coef(n, d) for n, d in zip(k2n, k2d)],
        }
    )
    df_dept.columns = pd.MultiIndex.from_tuples(df_dept.columns)

    year_dept_k1 = {"num": sum(k1n), "den": sum(k1d)}
    year_dept_k2 = {"num": sum(k2n), "den": sum(k2d)}
    managers = sorted(m for m in proj["manager"].dropna().unique())

    y_acc = {
        m: {"k1": {"num": 0.0, "den": 0.0}, "k2": {"num": 0.0, "den": 0.0}}
        for m in managers
    }
    for T in months:
        for mgr in managers:
            for key in ("k1", "k2"):
                y_acc[mgr][key]["num"] += store[mgr][T][key]["num"]
                y_acc[mgr][key]["den"] += store[mgr][T][key]["den"]

    rows_my = []
    for mgr in managers:
        y1, y2 = y_acc[mgr]["k1"], y_acc[mgr]["k2"]
        rows_my.append(
            {
                ("Менеджер", ""): mgr,
                col_tuples[0]: y1["den"],
                col_tuples[1]: y1["num"],
                col_tuples[2]: coef(y1["num"], y1["den"]),
                col_tuples[3]: y2["den"],
                col_tuples[4]: y2["num"],
                col_tuples[5]: coef(y2["num"], y2["den"]),
            }
        )
    df_mgr_year = pd.DataFrame(rows_my)
    df_mgr_year.columns = pd.MultiIndex.from_tuples(df_mgr_year.columns)

    col_labels = [RU_MONTH_LABEL[T.month] for T in months]
    mat_k1 = pd.DataFrame(index=managers, columns=col_labels, dtype=float)
    mat_k2 = pd.DataFrame(index=managers, columns=col_labels, dtype=float)

    for j, T in enumerate(months):
        cn = col_labels[j]
        for mgr in managers:
            a1 = store[mgr][T]["k1"]
            a2 = store[mgr][T]["k2"]
            mat_k1.loc[mgr, cn] = coef(a1["num"], a1["den"])
            mat_k2.loc[mgr, cn] = coef(a2["num"], a2["den"])

    dept_rows = [
        (
            period_ru(T),
            k1d[i],
            k1n[i],
            coef(k1n[i], k1d[i]),
            k2d[i],
            k2n[i],
            coef(k2n[i], k2d[i]),
        )
        for i, T in enumerate(months)
    ]
    mgr_rows = [
        (
            mgr,
            y_acc[mgr]["k1"]["den"],
            y_acc[mgr]["k1"]["num"],
            coef(y_acc[mgr]["k1"]["num"], y_acc[mgr]["k1"]["den"]),
            y_acc[mgr]["k2"]["den"],
            y_acc[mgr]["k2"]["num"],
            coef(y_acc[mgr]["k2"]["num"], y_acc[mgr]["k2"]["den"]),
        )
        for mgr in managers
    ]

    return ProlongationResult(
        fin_long=fin_long,
        proj=proj,
        ship_eff=ship_eff,
        exclude_stop_set=exclude_stop_set,
        exclusion_reasons=exclusion_reasons,
        months=months,
        managers=managers,
        dept_rows=dept_rows,
        mgr_rows=mgr_rows,
        mat_k1=mat_k1,
        mat_k2=mat_k2,
        year_dept_k1=year_dept_k1,
        year_dept_k2=year_dept_k2,
        df_dept=df_dept,
        df_mgr_year=df_mgr_year,
    )
