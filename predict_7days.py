import pandas as pd
import requests
from datetime import timedelta
import holidays # 🔥 [추가] 한국 휴일 계산을 위한 라이브러리 추가


def predict_7days(result, lat=37.530, lon=130.000):
    model = result['model']
    df = result['df']

    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=wind_speed_10m,pressure_msl&forecast_days=8&timezone=Asia%2FSeoul"
    marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&hourly=wave_height,wave_period,sea_surface_temperature&forecast_days=8&timezone=Asia%2FSeoul"

    w_res = requests.get(weather_url).json()
    m_res = requests.get(marine_url).json()

    df_w = pd.DataFrame(w_res['hourly'])
    df_m = pd.DataFrame(m_res['hourly'])
    df_w['time'] = pd.to_datetime(df_w['time'])
    df_m['time'] = pd.to_datetime(df_m['time'])

    weather_df = pd.merge(df_w, df_m, on='time', how='inner')
    weather_df['date'] = weather_df['time'].dt.date
    weather_daily = weather_df.groupby('date').agg({
        'wind_speed_10m': 'mean', 'pressure_msl': 'mean', 'sea_surface_temperature': 'mean',
        'wave_height': 'mean', 'wave_period': 'mean'
    }).reset_index()
    weather_daily.columns = ['date', 'ws1', 'pa', 'tw', 'wh_sig', 'wp']

    future_preds = []
    temp_df = df.copy()
    kr_holidays = holidays.KR()  # 🔥 [추가] 미래 예측용 휴일 달력 객체

    future_dates = pd.date_range(
        start=pd.Timestamp.today().normalize() + timedelta(days=1),
        periods=7
    )

    for i in range(7):

        future_date = future_dates[i]

        weather_row = weather_daily.iloc[
            min(i, len(weather_daily) - 1)
        ]

        # 🔥 [추가] 미래 특정 일자의 휴일 및 주말 여부 계산
        is_hol = 1 if future_date.date() in kr_holidays else 0
        is_next_hol = 1 if (future_date.date() + timedelta(days=1)) in kr_holidays else 0
        is_weekend = 1 if future_date.dayofweek in [4, 5] else 0

        # 🔥 [추가] 미래 기상 예보를 바탕으로 미래의 '결항 여부' 사전 계산
        is_canc = 1 if weather_row['pa'] >= 3.0 or weather_row['ws1'] >= 14.0 else 0
        lag_1_canc = temp_df.iloc[-1]['is_canceled']  # (전날)결항 여부

        # 🔥 [추가] 연속 결항일 계산 로직
        if is_canc == 1:
            consec_canc = temp_df.iloc[-1]['consecutive_canceled_days'] + 1 if lag_1_canc == 1 else 1
        else:
            consec_canc = 0

        # 🔥 [수정] 모델에 예측을 지시할 때, 방금 위에서 계산한 휴일/결항 변수를 포함시킴
        next_input = pd.DataFrame([{
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
            'is_holiday': is_hol,  # 새로 추가된 컬럼
            'is_day_before_holiday': is_next_hol,  # 새로 추가된 컬럼
            'is_weekend_demand': is_weekend,  # 새로 추가된 컬럼
            'is_canceled': is_canc,  # 새로 추가된 컬럼
            'lag_1_canceled': lag_1_canc,  # 새로 추가된 컬럼
            'consecutive_canceled_days': consec_canc  # 새로 추가된 컬럼
        }])

        pred_price = model.predict(next_input)[0]
        future_preds.append({'위판일자': future_date, '예측단가': pred_price})

        new_row = temp_df.iloc[-1].copy()
        new_row['위판일자'] = future_date
        new_row['단가'] = pred_price

        # 🔥 [추가] 내일의 예측을 위해 '오늘 결항 상태'를 DataFrame에 기록해둠
        new_row['is_canceled'] = is_canc
        new_row['consecutive_canceled_days'] = consec_canc
        temp_df = pd.concat([temp_df, pd.DataFrame([new_row])], ignore_index=True)

    pred_df = pd.DataFrame(future_preds)
    return pred_df