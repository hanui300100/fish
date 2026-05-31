import pandas as pd
import requests
from datetime import datetime, timedelta
import os
import numpy as np
from dotenv import load_dotenv

# .env 파일에서 환경변수 불러오기
load_dotenv()


def update_weather_data(station='22105'):
    # 환경변수에서 기상청 인증키 가져오기
    auth_key = os.getenv('WEATHER_API_KEY')

    if not auth_key:
        print("🚨 에러: .env 파일에서 WEATHER_API_KEY를 찾을 수 없습니다!")
        return None

    try:
        df1 = pd.read_csv('날씨.csv')
        last_date = pd.to_datetime(df1['date']).max()
        start_date = last_date + timedelta(hours=1)
    except FileNotFoundError:
        df1 = pd.DataFrame()
        start_date = datetime.now() - timedelta(days=30)

    end_date = datetime.now()

    if start_date.date() >= end_date.date():
        print("이미 최신 기상 데이터입니다.")
        return None

    tm1 = start_date.strftime("%Y%m%d%H%M")
    tm2 = end_date.strftime("%Y%m%d%H%M")
    url = f"https://apihub.kma.go.kr/api/typ01/url/kma_buoy2.php?tm1={tm1}&tm2={tm2}&stn={station}&help=0&authKey={auth_key}"

    try:
        response = requests.get(url, timeout=60)
        if response.status_code != 200: return None
        raw_text = response.text
    except Exception as e:
        print(f"기상청 API 호출 에러: {e}")
        return None

    lines = raw_text.split("\n")
    data_lines = [line.strip() for line in lines if line.strip() and not line.startswith("#")]

    if not data_lines:
        return None

    columns = ["datetime", "stn", "wd1", "ws1", "ws1_gst", "wd2", "ws2", "ws2_gst",
               "pa", "hm", "ta", "tw", "wh_max", "wh_sig", "wh_ave", "wp", "wo", "aqc", "mqc", "end"]

    data = [line.split(",") for line in data_lines]
    df = pd.DataFrame(data, columns=columns).drop(columns=["end"], errors='ignore')

    # 숫자형 변환
    numeric_cols = ["ws1", "pa", "ta", "tw", "wh_sig", "wp"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 기상청 이상치(-99.9, -99) 처리
    df.replace([-99.9, -99.0], np.nan, inplace=True)

    # 날짜 파싱 (datetime 컬럼을 연월일로)
    df['date'] = pd.to_datetime(df['datetime'], format='%Y%m%d%H%M').dt.date

    # 일별 평균 계산
    df_daily = df.groupby('date')[numeric_cols].mean().reset_index()

    # 기존 날씨.csv와 병합
    if not df1.empty:
        df_daily['date'] = pd.to_datetime(df_daily['date'])
        df1['date'] = pd.to_datetime(df1['date'])
        updated_df = pd.concat([df1, df_daily], ignore_index=True)
        updated_df.drop_duplicates(subset=['date'], keep='last', inplace=True)
        updated_df = updated_df.sort_values('date').reset_index(drop=True)
    else:
        updated_df = df_daily

    # 저장
    updated_df.to_csv('날씨.csv', index=False, encoding='utf-8-sig')
    print("날씨 데이터 업데이트 완료")
    return updated_df