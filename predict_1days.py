import pandas as pd
import requests
from datetime import timedelta
import holidays


def predict_1days(result, lat=37.530, lon=130.000):
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
        'wind_speed_10m': 'mean', 'pressure_msl': 'mean',
        'sea_surface_temperature': 'mean', 'wave_height': 'mean', 'wave_period': 'mean'
    }).reset_index()

    weather_daily.columns = ['date', 'ws1', 'pa', 'tw', 'wh_sig', 'wp']

    temp_df = df.copy()
    kr_holidays = holidays.KR()

    future_date = temp_df['위판일자'].max() + timedelta(days=1)

    # 🔥 핵심 에러 해결: 기상청 API가 오늘 날씨만 주더라도 에러가 나지 않게 방어
    safe_index = min(1, len(weather_daily) - 1)
    weather_row = weather_daily.iloc[safe_index]

    is_hol = 1 if future_date.date() in kr_holidays else 0
    is_next_hol = 1 if (future_date.date() + timedelta(days=1)) in kr_holidays else 0
    is_weekend = 1 if future_date.dayofweek in [4, 5] else 0

    is_canc = 1 if weather_row['pa'] >= 3.0 or weather_row['ws1'] >= 14.0 else 0
    lag_1_canc = temp_df.iloc[-1]['is_canceled']

    if is_canc == 1:
        consec_canc = temp_df.iloc[-1]['consecutive_canceled_days'] + 1 if lag_1_canc == 1 else 1
    else:
        consec_canc = 0

    next_input = pd.DataFrame([{
        'lag_1': temp_df.iloc[-1]['단가'],
        'lag_7': temp_df.iloc[-7]['단가'] if len(temp_df) >= 7 else temp_df.iloc[-1]['단가'],
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
    }])

    pred_price = model.predict(next_input)[0]
    future_preds = [{'위판일자': future_date, '예측단가': pred_price}]
    pred_df = pd.DataFrame(future_preds)

    return pred_df