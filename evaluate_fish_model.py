import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import holidays # 🔥 [추가] 한국 휴일 계산을 위한 라이브러리 추가

from xgboost import XGBRegressor

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)


def evaluate_fish_model(fish_name):
    df = pd.read_csv(f'fish_daily/{fish_name}.csv')
    wt = pd.read_csv('날씨.csv')

    df['위판일자'] = pd.to_datetime(df['위판일자'])
    wt['date'] = pd.to_datetime(wt['date'])

    df = pd.merge(df, wt, left_on='위판일자', right_on='date', how='left').drop(columns=['date'])
    df = df.sort_values('위판일자')

    # 기존 파생 변수
    df['lag_1'] = df['단가'].shift(1)
    df['lag_7'] = df['단가'].shift(7)
    df['rolling_mean_7'] = df['단가'].rolling(7).mean()
    df['month'] = df['위판일자'].dt.month
    df['dayofweek'] = df['위판일자'].dt.dayofweek

    # 🔥 [추가] 휴일/명절 파생 변수 (수요 폭등 반영)
    kr_holidays = holidays.KR()
    df['is_holiday'] = df['위판일자'].dt.date.apply(lambda x: 1 if x in kr_holidays else 0)
    df['is_day_before_holiday'] = df['is_holiday'].shift(-1).fillna(0) # 내일이 휴일인가?
    df['is_weekend_demand'] = df['위판일자'].dt.dayofweek.apply(lambda x: 1 if x in [4, 5] else 0) # 금,토 수요

    # 🔥 [추가] 기상 결항 파생 변수 (공급 부족 반영, 파고 3m 또는 풍속 14m/s 이상 시)
    df['is_canceled'] = df.apply(lambda x: 1 if x['pa'] >= 3.0 or x['ws1'] >= 14.0 else 0, axis=1)
    df['lag_1_canceled'] = df['is_canceled'].shift(1).fillna(0) # 어제 결항이었나?
    df['consecutive_canceled_days'] = df['is_canceled'].groupby((df['is_canceled'] == 0).cumsum()).cumsum() # 연속 결항일

    df = df.dropna()

    # 🔥 [수정] 새로 생성된 파생 변수들을 모델 학습(features) 리스트에 포함
    features = [
        'lag_1', 'lag_7', 'rolling_mean_7', 'month', 'dayofweek',
        'ws1', 'pa', 'tw', 'wh_sig', 'wp',
        'is_holiday', 'is_day_before_holiday', 'is_weekend_demand',
        'is_canceled', 'lag_1_canceled', 'consecutive_canceled_days'
    ]

    X = df[features]
    y = df['단가']

    model = XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=6, random_state=42)
    model.fit(X, y)
    pred = model.predict(X)

    mae = mean_absolute_error(y, pred)
    rmse = np.sqrt(mean_squared_error(y, pred))
    r2 = r2_score(y, pred)

    print(f'{fish_name} 모델 평가 - MAE: {mae:.2f} / RMSE: {rmse:.2f} / R2: {r2:.4f}')

    return {'model': model, 'df': df, 'features': features}