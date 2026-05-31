#어종 분리 코드
import os
import pandas as pd

def split_fish_data(input_file='data3_historical_master.csv', save_dir='fish_split'):
    df = pd.read_csv(input_file)
    df['위판일자'] = pd.to_datetime(df['위판일자'])
    os.makedirs(save_dir, exist_ok=True)
    df['수산물표준코드명'] = df['수산물표준코드명'].astype(str).str.strip()

    for fish, group in df.groupby('수산물표준코드명'):
        file_path = os.path.join(save_dir, f'{fish}.csv')
        group = group.sort_values('위판일자').reset_index(drop=True)
        group.to_csv(file_path, index=False, encoding='utf-8-sig')
    print('전체 어종 분리 완료')