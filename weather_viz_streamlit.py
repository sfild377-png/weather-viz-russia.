# weather_viz_streamlit.py
import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Погода по регионам РФ (2015–2025)",
    layout="wide"
)

st.title("🌤️ Система визуализации данных о погоде по регионам РФ")
st.markdown("Анализ исторических данных (реальных или синтетических) за 2015–2025 гг.")

# Список городов
CITIES = {
    "Москва": (55.7558, 37.6176),
    "Санкт-Петербург": (59.9343, 30.3351),
    "Новосибирск": (55.0084, 82.9357),
    "Екатеринбург": (56.8389, 60.6057),
    "Казань": (55.8304, 49.0661),
    "Нижний Новгород": (56.2965, 43.9361),
    "Челябинск": (55.1644, 61.4368),
    "Самара": (53.1959, 50.1001),
    "Омск": (54.9888, 73.3686),
    "Ростов-на-Дону": (47.2357, 39.7015),
    "Уфа": (54.7348, 55.9578),
    "Красноярск": (56.0184, 92.8672),
    "Воронеж": (51.6720, 39.1843),
    "Пермь": (58.0105, 56.2502),
    "Волгоград": (48.7080, 44.5133),
}

def generate_synthetic_data(city_name, lat, years=11):
    """Генерирует правдоподобные синтетические данные, если API недоступен"""
    np.random.seed(hash(city_name) % 2**32)
    base_temp = np.random.uniform(-8, 4)  # среднегодовая темп-ра для региона
    all_dates = []
    all_temps = []
    all_precip = []
    
    for year in range(2015, 2015 + years):
        for month in range(1, 13):
            # Генерация дней в месяце
            days_in_month = pd.Period(f"{year}-{month:02d}").days_in_month
            for day in range(1, days_in_month + 1):
                date = datetime(year, month, day)
                # Сезонная температура
                seasonal = 22 * np.sin(2 * np.pi * (month - 1) / 12 - np.pi/2)
                trend = 0.12 * (year - 2015)  # потепление
                temp = base_temp + seasonal + trend + np.random.normal(0, 3)
                precip = np.random.gamma(1.5, 3) if month in [6,7,8] else np.random.gamma(1, 2)
                all_dates.append(date)
                all_temps.append(round(temp, 2))
                all_precip.append(round(precip, 2))
    
    df = pd.DataFrame({
        "date": all_dates,
        "temperature": all_temps,
        "precipitation": all_precip,
        "city": city_name
    })
    return df

@st.cache_data(ttl=7200)  # кэш на 2 часа
def fetch_or_generate_data(lat, lon, city_name):
    """Пытается загрузить реальные данные. При ошибке — возвращает синтетические."""
    start_date = "2015-01-01"
    end_date = (datetime.now().date() - timedelta(days=1)).isoformat()
    
    # Попытка загрузить реальные данные
    try:
        with st.spinner(f"🌐 Загрузка реальных данных для {city_name}..."):
            response = requests.get(
                "https://archive-api.open-meteo.com/v1/archive",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": start_date,
                    "end_date": end_date,
                    "daily": ["temperature_2m_mean", "precipitation_sum"],
                    "timezone": "Europe/Moscow"
                },
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            if "daily" in data and data["daily"]["time"]:
                df = pd.DataFrame({
                    "date": pd.to_datetime(data["daily"]["time"]),
                    "temperature": data["daily"]["temperature_2m_mean"],
                    "precipitation": data["daily"]["precipitation_sum"],
                    "city": city_name
                })
                st.success(f"✅ Реальные данные получены для {city_name}")
                return df
    except Exception as e:
        st.warning(f"⚠️ Не удалось загрузить реальные данные для {city_name}. Причина: {str(e)[:100]}... Используем синтетические данные.")
    
    # Если не получилось — возвращаем синтетику
    return generate_synthetic_data(city_name, lat)

# Выбор регионов
selected_cities = st.sidebar.multiselect(
    "Выберите регионы (города):",
    list(CITIES.keys()),
    default=["Москва", "Санкт-Петербург"]
)

if not selected_cities:
    st.info("Пожалуйста, выберите хотя бы один регион.")
    st.stop()

# Загрузка данных
all_data = []
for city in selected_cities:
    lat, lon = CITIES[city]
    df = fetch_or_generate_data(lat, lon, city)
    all_data.append(df)

df_full = pd.concat(all_data, ignore_index=True)

# График температуры
st.subheader("Средняя температура по регионам (сглаженная)")
fig_temp = go.Figure()
for city in selected_cities:
    city_df = df_full[df_full["city"] == city].sort_values("date")
    city_df["temp_smooth"] = city_df["temperature"].rolling(window=30, center=True).mean()
    fig_temp.add_trace(go.Scatter(
        x=city_df["date"],
        y=city_df["temp_smooth"],
        mode='lines',
        name=city
    ))
fig_temp.update_layout(xaxis_title="Дата", yaxis_title="Температура (°C)")
st.plotly_chart(fig_temp, use_container_width=True)

# График осадков
st.subheader("Годовые осадки")
df_full["year"] = df_full["date"].dt.year
df_yearly = df_full.groupby(["city", "year"])["precipitation"].sum().reset_index()

fig_precip = go.Figure()
for city in selected_cities:
    city_df = df_yearly[df_yearly["city"] == city]
    fig_precip.add_trace(go.Bar(x=city_df["year"], y=city_df["precipitation"], name=city))
fig_precip.update_layout(xaxis_title="Год", yaxis_title="Осадки (мм)", barmode="group")
st.plotly_chart(fig_precip, use_container_width=True)

# Экспорт
st.sidebar.markdown("---")
st.sidebar.download_button(
    "📥 Скачать все данные (CSV)",
    df_full.to_csv(index=False, encoding="utf-8"),
    "weather_data_russia.csv",
    "text/csv"
)

st.sidebar.markdown("""
---
ℹ️ **Источник данных**:  
- 🌐 Реальные: [Open-Meteo](https://open-meteo.com/)  
- 🧪 Синтетические: если API недоступен  
🕒 Период: 2015–2025 (или до вчерашнего дня)  
🔁 Данные кэшируются на 2 часа
""")