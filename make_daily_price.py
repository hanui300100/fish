import pandas as pd
import os


def make_daily_price(fish_name):
    df = pd.read_csv(f'fish_split/{fish_name}.csv')
    df['위판일자'] = pd.to_datetime(df['위판일자'])

    if '단가' not in df.columns:
        df['단가'] = df['위판금액'] / df['위판중량']

    df = df[df['위판중량'] > 0]

    # 데이터가 5건 이상일 때만 이상치를 자릅니다 (너무 적을 때 자르면 데이터가 소멸됨)
    if len(df) > 5:
        Q1 = df['단가'].quantile(0.25)
        Q3 = df['단가'].quantile(0.75)
        df_clean = df[(df['단가'] >= Q1) & (df['단가'] <= Q3)].copy()
    else:
        df_clean = df.copy()

    # 데이터가 0건이라면 빈 뼈대만 만듭니다
    if len(df_clean) == 0:
        df_daily = pd.DataFrame(columns=['위판일자', '단가'])
        os.makedirs('fish_daily', exist_ok=True)
        df_daily.to_csv(f'fish_daily/{fish_name}.csv', index=False, encoding='utf-8-sig')
        return df_daily

    # 🔥 곰치_꼼치 에러 해결: apply 대신 agg를 사용하여 안전하게 병합
    df_clean['총액'] = df_clean['단가'] * df_clean['위판중량']
    grouped = df_clean.groupby('위판일자').agg({'총액': 'sum', '위판중량': 'sum'}).reset_index()
    grouped['단가'] = grouped['총액'] / grouped['위판중량']

    df_daily = grouped[['위판일자', '단가']].sort_values('위판일자')
    os.makedirs('fish_daily', exist_ok=True)
    df_daily.to_csv(f'fish_daily/{fish_name}.csv', index=False, encoding='utf-8-sig')
    return df_daily