import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import holidays  # 🔥 [추가] 한국 휴일 계산을 위한 라이브러리 추가

from env_loader import get_env_value


def update_fish_data(service_key=None, min_daily_count=0):
    if service_key is None:
        service_key = get_env_value('PUBLIC_DATA_API_KEY', 'PUBLIC_DATA_API_KET')

    try:
        # 통합 마스터 파일로 파일명 통일
        df = pd.read_csv('data3_historical_master.csv')
    except FileNotFoundError:
        df = pd.DataFrame(columns=['위판일자', '산지조합명', '수산물표준코드명', '위판중량', '위판금액', '단가'])

    url = 'http://apis.data.go.kr/1192000/select0040List/getselect0040List'
    markets = ['강릉시수산업협동조합', '강원고성군수산업협동조합', '동해시수산업협동조합', '삼척수산업협동조합',
               '속초시수산업협동조합', '양양수산업협동조합', '죽변수산업협동조합', '영덕북부수산업협동조합', '포항수산업협동조합']

    # 🔥 [수정] 13종 통합 어종 수집 리스트 (API 호출용 키워드)
    fish_list = ['문어', '가자미', '넙치', '대게', '대구', '아귀', '골뱅이', '방어', '살오징어', '홍게', '붉은대게', '청어', '화살꼴뚜기']

    if not df.empty:
        df['위판일자'] = pd.to_datetime(df['위판일자'])
        last_date = df['위판일자'].max()
        start_date = last_date + timedelta(days=1)
    else:
        start_date = datetime.today() - timedelta(days=30)

    end_date = datetime.today() - timedelta(days=1)

    if start_date > end_date:
        print("이미 최신 데이터입니다.")
        return 0

    print(f"{start_date.date()} ~ {end_date.date()} 데이터 수집 시작")
    all_items = []
    current_date = start_date

    while current_date <= end_date:
        baseDt = current_date.strftime('%Y%m%d')
        daily_items = []
        for market in markets:
            for fish in fish_list:
                params = {
                    'serviceKey': service_key, 'numOfRows': '100', 'type': 'xml',
                    'baseDt': baseDt, 'mxtrNm': market, 'mprcStdCodeNm': fish
                }
                try:
                    for page in range(1, 6):
                        params['pageNo'] = str(page)
                        response = requests.get(url, params=params, timeout=5)
                        if response.status_code != 200: break

                        root = ET.fromstring(response.content.decode('utf-8'))
                        items = root.findall('.//item')
                        if not items: break

                        for item in items:
                            weight = float(item.findtext('csmtWt', 0) or 0)
                            amount = int(item.findtext('csmtAmount', 0) or 0)
                            if weight <= 0: continue

                            daily_items.append({
                                "위판일자": item.findtext('csmtDe'),
                                "산지조합명": market,
                                "수산물표준코드명": item.findtext('mprcStdCodeNm'),
                                "위판중량": weight,
                                "위판금액": amount,
                                "단가": amount / weight
                            })
                except Exception as e:
                    pass

        if len(daily_items) > min_daily_count:
            all_items.extend(daily_items)
            print(f"{baseDt} 완료 ({len(daily_items)}개)")
        else:
            print(f"{baseDt} 데이터 부족 ({len(daily_items)}개)")

        current_date += timedelta(days=1)

    if len(all_items) == 0:
        print("신규 데이터 없음")
        return 0

    new_df = pd.DataFrame(all_items)
    new_df['위판일자'] = pd.to_datetime(new_df['위판일자'])

    updated_df = pd.concat([df, new_df], ignore_index=True)
    updated_df = updated_df.sort_values('위판일자').reset_index(drop=True)
    updated_df['수산물표준코드명'] = updated_df['수산물표준코드명'].astype(str).str.strip()

    # 🔥 [수정] 13종 통합 필터링 리스트
    target_fish = ['문어', '대문어', '가자미류', '기름가자미', '참가자미', '홍가자미', '대구', '대구류', '아귀', '넙치', '대게', '가자미',
                   '골뱅이', '방어', '살오징어', '홍게', '붉은대게', '청어', '화살꼴뚜기']
    df_filter = updated_df[updated_df['수산물표준코드명'].isin(target_fish)].copy()

    # 🔥 [수정] 13종 통합 명칭 매핑 규칙 (곰치_꼼치 및 붉은대게 통합 반영)
    fish_map = {
        '대문어': '문어',
        '기름가자미': '가자미', '참가자미': '가자미', '홍가자미': '가자미', '가자미류': '가자미',
        '대구류': '대구',
        '홍게': '붉은대게'
    }
    df_filter['수산물표준코드명'] = df_filter['수산물표준코드명'].replace(fish_map)

    # 가중평균 병합
    df_grouped = df_filter.groupby(['위판일자', '산지조합명', '수산물표준코드명'], as_index=False)[['위판중량', '위판금액']].sum()
    df_grouped['단가'] = df_grouped['위판금액'] / df_grouped['위판중량']
    df_filter = df_grouped.sort_values(['위판일자', '산지조합명', '수산물표준코드명']).reset_index(drop=True)

    df_filter.to_csv('data3_historical_master.csv', index=False, encoding='utf-8-sig')
    print("통합 마스터 데이터 업데이트 완료")
