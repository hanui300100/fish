import pandas as pd
import requests
from datetime import timedelta

from datetime import timedelta
import holidays
import pandas as pd
import requests


def predict_1days(result, lat=37.530, lon=130.000):
    # 🔥 모델 / 데이터 가져오기
    model = result['model']
    df = result['df']

    # 🔥 미래 날씨 예보 가져오기
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}"
        f"&longitude={lon}"
        f"&hourly=wind_speed_10m,pressure_msl"
        f"&forecast_days=8"
        f"&timezone=Asia%2FSeoul"
    )

    marine_url = (
        f"https://marine-api.open-meteo.com/v1/marine?"
        f"latitude={lat}"
        f"&longitude={lon}"
        f"&hourly=wave_height,wave_period,sea_surface_temperature"
        f"&forecast_days=8"
        f"&timezone=Asia%2FSeoul"
    )

    # 🔥 요청
    w_res = requests.get(weather_url).json()
    m_res = requests.get(marine_url).json()

    # 🔥 DataFrame 생성
    df_w = pd.DataFrame(w_res['hourly'])
    df_m = pd.DataFrame(m_res['hourly'])

    df_w['time'] = pd.to_datetime(df_w['time'])
    df_m['time'] = pd.to_datetime(df_m['time'])

    # 🔥 병합
    weather_df = pd.merge(df_w, df_m, on='time', how='inner')

    # 🔥 날짜 컬럼
    weather_df['date'] = weather_df['time'].dt.date

    # 🔥 일평균
    weather_daily = (
        weather_df.groupby('date')
        .agg(
            {
                'wind_speed_10m': 'mean',
                'pressure_msl': 'mean',
                'sea_surface_temperature': 'mean',
                'wave_height': 'mean',
                'wave_period': 'mean',
            }
        )
        .reset_index()
    )

    # 🔥 컬럼명 통일
    weather_daily.columns = ['date', 'ws1', 'pa', 'tw', 'wh_sig', 'wp']

    # =========================
    # 🔥 미래 1일 예측
    # =========================

    temp_df = df.copy()
    kr_holidays = holidays.KR()

    # 🔥 데이터의 마지막 날짜 + 1일 (내일)
    future_date = temp_df['위판일자'].max() + timedelta(days=1)

    # 🔥 내일(index 1)의 날씨 데이터 추출
    weather_row = weather_daily.iloc[1]

    # 🔥 휴일 및 주말 여부 계산
    is_hol = 1 if future_date.date() in kr_holidays else 0
    is_next_hol = (
        1 if (future_date.date() + timedelta(days=1)) in kr_holidays else 0
    )
    is_weekend = 1 if future_date.dayofweek in [4, 5] else 0

    # 🔥 결항 여부 및 연속 결항일 계산
    is_canc = (
        1 if weather_row['pa'] >= 3.0 or weather_row['ws1'] >= 14.0 else 0
    )
    lag_1_canc = temp_df.iloc[-1]['is_canceled']

    if is_canc == 1:
        consec_canc = (
            temp_df.iloc[-1]['consecutive_canceled_days'] + 1
            if lag_1_canc == 1
            else 1
        )
    else:
        consec_canc = 0

    # 🔥 feature 생성
    next_input = pd.DataFrame(
        [
            {
                'lag_1': temp_df.iloc[-1]['단가'],
                'lag_7': temp_df.iloc[-7]['단가'],
                'rolling_mean_7': temp_df['단가'].tail(7).mean(),
                'month': future_date.month,
                'dayofweek': future_date.dayofweek,
                'ws1': weather_row['ws1'],
                'pa': weather_row['pa'],
                'tw': weather_row['tw'],
                'wh_sig': weather_row['wh_sig'],
                'wp': weather_row['wp'],
                'is_holiday': is_hol,
                'is_day_before_holiday': is_next_hol,
                'is_weekend_demand': is_weekend,
                'is_canceled': is_canc,
                'lag_1_canceled': lag_1_canc,
                'consecutive_canceled_days': consec_canc,
            }
        ]
    )

    # 🔥 예측
    pred_price = model.predict(next_input)[0]

    # 🔥 저장
    future_preds = [
        {
            '위판일자': future_date,
            '예측단가': pred_price
        }
    ]

    # 🔥 결과 DataFrame
    pred_df = pd.DataFrame(future_preds)

    print(pred_df)

    return pred_df