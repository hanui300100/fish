#이상치 제거 및 일별 가중평균 단가 계산 함수
import pandas as pd
import os

def make_daily_price(fish_name):
    df = pd.read_csv(f'fish_split/{fish_name}.csv')
    df['위판일자'] = pd.to_datetime(df['위판일자'])
    if '단가' not in df.columns:
        df['단가'] = df['위판금액'] / df['위판중량']

    df = df[df['위판중량'] > 0]
    Q1 = df['단가'].quantile(0.25)
    Q3 = df['단가'].quantile(0.75)
    df_clean = df[(df['단가'] >= Q1) & (df['단가'] <= Q3)]

    df_daily = df_clean.groupby('위판일자').apply(
        lambda x: (x['단가'] * x['위판중량']).sum() / x['위판중량'].sum(), include_groups=False
    ).reset_index(name='단가')

    df_daily = df_daily.sort_values('위판일자')
    os.makedirs('fish_daily', exist_ok=True)
    df_daily.to_csv(f'fish_daily/{fish_name}.csv', index=False, encoding='utf-8-sig')
    return df_daily