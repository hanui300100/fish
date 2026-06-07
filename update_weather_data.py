import pandas as pd
import requests
from datetime import datetime, timedelta

from env_loader import get_env_value


# 날짜 데이터 최신화 코드
def update_weather_data(station='22105', auth_key=None):
    if auth_key is None:
        auth_key = get_env_value('WEATHER_API_KEY')

    try:
        df1 = pd.read_csv('날씨.csv')
        last_date = pd.to_datetime(df1['date']).max()
        start_date = last_date + timedelta(hours=1)
    except FileNotFoundError:
        df1 = pd.DataFrame()
        start_date = datetime.now() - timedelta(days=30)

    end_date = datetime.now()

    if start_date.date() >= end_date.date():
        return None

    tm1 = start_date.strftime("%Y%m%d%H%M")
    tm2 = end_date.strftime("%Y%m%d%H%M")
    url = f"https://apihub.kma.go.kr/api/typ01/url/kma_buoy2.php?tm1={tm1}&tm2={tm2}&stn={station}&help=0&authKey={auth_key}"

    try:
        response = requests.get(url, timeout=60)
        if response.status_code != 200: return None
        raw_text = response.text
    except:
        return None

    lines = raw_text.split("\n")
    data_lines = [line.strip() for line in lines if line.strip() and not line.startswith("#")]

    columns = ["datetime", "stn", "wd1", "ws1", "ws1_gst", "wd2", "ws2", "ws2_gst",
               "pa", "hm", "ta", "tw", "wh_max", "wh_sig", "wh_ave", "wp", "wo", "aqc", "mqc", "end"]

    data = [line.split(",") for line in data_lines]
    df = pd.DataFrame(data, columns=columns).drop(columns=["end"])

    numeric_cols = df.columns.drop(["datetime", "aqc", "mqc"])
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y%m%d%H%M")

    df['date'] = df['datetime'].dt.date
    df_daily = df.groupby('date').agg(
        {'ws1': 'mean', 'pa': 'mean', 'tw': 'mean', 'wh_sig': 'mean', 'wp': 'mean'}).reset_index()

    updated_df = pd.concat([df1, df_daily], ignore_index=True).drop_duplicates(subset=['date'])
    updated_df.to_csv('날씨.csv', index=False, encoding='utf-8-sig')
