import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import holidays

from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def evaluate_fish_model(fish_name):
    df = pd.read_csv(f'fish_daily/{fish_name}.csv')
    wt = pd.read_csv('날씨.csv')

    df['위판일자'] = pd.to_datetime(df['위판일자'])
    wt['date'] = pd.to_datetime(wt['date'])

    df = pd.merge(df, wt, left_on='위판일자', right_on='date', how='left').drop(columns=['date'])
    df = df.sort_values('위판일자')

    if len(df) > 0:
        df['단가'] = df['단가'].ffill().bfill()
        wt_cols = ['ws1', 'pa', 'tw', 'wh_sig', 'wp']
        for col in wt_cols:
            if col in df.columns:
                df[col] = df[col].ffill().bfill()

    # 파생 변수
    df['lag_1'] = df['단가'].shift(1)
    df['lag_7'] = df['단가'].shift(7)
    df['rolling_mean_7'] = df['단가'].rolling(7).mean()
    df['month'] = df['위판일자'].dt.month
    df['dayofweek'] = df['위판일자'].dt.dayofweek

    kr_holidays = holidays.KR()
    df['is_holiday'] = df['위판일자'].dt.date.apply(lambda x: 1 if x in kr_holidays else 0)
    df['is_day_before_holiday'] = df['is_holiday'].shift(-1).fillna(0)
    df['is_weekend_demand'] = df['위판일자'].dt.dayofweek.apply(lambda x: 1 if x in [4, 5] else 0)

    df['is_canceled'] = df.apply(lambda x: 1 if x.get('pa', 0) >= 3.0 or x.get('ws1', 0) >= 14.0 else 0, axis=1)
    df['lag_1_canceled'] = df['is_canceled'].shift(1).fillna(0)
    df['consecutive_canceled_days'] = df['is_canceled'].groupby((df['is_canceled'] == 0).cumsum()).cumsum()

    # 🔥 핵심 에러 해결: dropna() 대신 강제로 빈칸을 메워 데이터 증발 방지
    df = df.bfill().ffill().fillna(0)

    if len(df) == 0:
        raise ValueError("학습할 유효한 데이터가 없습니다.")

    features = [
        'lag_1', 'lag_7', 'rolling_mean_7', 'month', 'dayofweek',
        'ws1', 'pa', 'tw', 'wh_sig', 'wp',
        'is_holiday', 'is_day_before_holiday', 'is_weekend_demand',
        'is_canceled', 'lag_1_canceled', 'consecutive_canceled_days'
    ]

    # 혹시 날씨 데이터가 완전히 누락된 경우를 대비한 안전망
    for f in features:
        if f not in df.columns:
            df[f] = 0

    X = df[features]
    y = df['단가']

    model = XGBRegressor(n_estimators=100, learning_rate=0.05, max_depth=3, random_state=42)
    model.fit(X, y)
    pred = model.predict(X)

    mae = mean_absolute_error(y, pred)
    rmse = np.sqrt(mean_squared_error(y, pred))
    r2 = r2_score(y, pred) if len(y) > 1 else 0.0

    print(f'{fish_name} 모델 평가 - MAE: {mae:.2f} / RMSE: {rmse:.2f} / R2: {r2:.4f}')

    return {'model': model, 'df': df, 'features': features}