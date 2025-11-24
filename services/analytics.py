import io
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from database import core as db

plt.style.use('dark_background')

def _date_range(days: int):
    today = datetime.utcnow().date()
    return [today - timedelta(days=i) for i in reversed(range(days))]


async def generate_revenue_chart(days: int = 30) -> io.BytesIO:
    series = await db.get_revenue_timeseries(days)
    dates = _date_range(days)
    df = pd.DataFrame({
        "date": pd.to_datetime([d for d in dates]),
        "revenue": [series.get(d.isoformat(), 0) for d in dates],
    })
    df["label"] = df["date"].dt.strftime("%d.%m")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df["label"], df["revenue"], color="#7ed957", linewidth=2.5, marker="o")
    ax.fill_between(df["label"], df["revenue"], color="#7ed957", alpha=0.1)
    ax.set_title("Доход по дням", fontsize=14)
    ax.set_ylabel("₽")
    ax.set_xticklabels(df["label"], rotation=45, ha="right")
    ax.grid(alpha=0.2, linestyle="--")
    fig.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


async def generate_services_pie_chart() -> io.BytesIO:
    distribution = await db.get_service_distribution()
    labels = list(distribution.keys())
    values = list(distribution.values())
    if not labels:
        labels, values = ["Нет данных"], [1]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.pie(values, labels=labels, autopct="%1.0f%%", startangle=140)
    ax.set_title("Популярность услуг")
    fig.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


async def generate_funnel_chart(days: int = 30) -> io.BytesIO:
    funnel = await db.get_funnel_counts(days)
    labels = ["/start", "Прайс", "Консультация", "Заказ"]
    keys = ["start", "price_list", "consult", "order_submit"]
    values = [funnel.get(k, 0) for k in keys]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, values, color=["#5dade2", "#58d68d", "#f4d03f", "#e74c3c"])
    ax.bar_label(bars)
    ax.set_title("Воронка продаж (30д)")
    ax.set_ylabel("Кол-во событий")
    ax.grid(axis="y", alpha=0.2, linestyle="--")
    fig.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf
