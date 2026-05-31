import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pandas as pd
import time
from dotenv import load_dotenv

# .env 파일에서 환경변수 불러오기
load_dotenv()


def update_fish_data(min_daily_count=50):
    # 코드에 API 키를 하드코딩하지 않고 환경변수에서 가져옵니다.
    service_key = os.getenv('PUBLIC_DATA_API_KEY')

    if not service_key:
        print("🚨 에러: .env 파일에서 PUBLIC_DATA_API_KEY를 찾을 수 없습니다!")
        return 0

    try:
        # 통합 마스터 파일로 파일명 통일
        df = pd.read_csv('data3_historical_master.csv')
    except FileNotFoundError:
        df = pd.DataFrame(columns=['위판일자', '산지조합명', '수산물표준코드명', '위판중량', '위판금액', '단가'])

    url = 'http://apis.data.go.kr/1192000/select0040List/getselect0040List'
    markets = ['강릉시수산업협동조합', '강원고성군수산업협동조합', '동해시수산업협동조합', '삼척수산업협동조합',
               '속초시수산업협동조합', '양양수산업협동조합', '죽변수산업협동조합', '영덕북부수산업협동조합', '포항수산업협동조합']

    # 🔥 13종 통합 필터링 리스트
    fish_list = ['문어', '가자미', '넙치', '대게', '대구', '아귀', '골뱅이', '방어', '살오징어', '곰치', '꼼치', '홍게', '붉은대게', '청어', '화살꼴뚜기']

    if not df.empty:
        df['위판일자'] = pd.to_datetime(df['위판일자'])
        last_date = df['위판일자'].max()
        start_date = last_date + timedelta(days=1)
    else:
        start_date = datetime.today() - timedelta(days=30)

    end_date = datetime.today() - timedelta(days=1)

    if start_date > end_date:
        print("이미 최신 수산물 데이터입니다.")
        return 0

    print(f"{start_date.date()} ~ {end_date.date()} 수산물 데이터 수집 시작")
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

                        # 🔥 3회 재시도 (Retry) 로직
                        max_retries = 3
                        success = False

                        for attempt in range(max_retries):
                            try:
                                response = requests.get(url, params=params, timeout=10)
                                if response.status_code == 200:
                                    success = True
                                    break
                                else:
                                    print(
                                        f"[{market} - {fish}] API 상태코드 {response.status_code}. 3초 후 재시도 ({attempt + 1}/{max_retries})")
                                    time.sleep(3)
                            except requests.exceptions.RequestException:
                                print(f"[{market} - {fish}] 통신 지연 에러 발생. 3초 후 재시도 ({attempt + 1}/{max_retries})")
                                time.sleep(3)

                        if not success:
                            print(f"🚨 [{market} - {fish}] 3회 재시도 최종 실패. 해당 페이지 건너뜀.")
                            break

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

    # 🔥 13종 전처리 필터링 및 이름 매핑 통합
    target_fish = ['문어', '대문어', '가자미류', '기름가자미', '참가자미', '홍가자미', '대구', '대구류', '아귀', '넙치', '대게', '가자미',
                   '골뱅이', '방어', '살오징어', '곰치', '꼼치', '홍게', '붉은대게', '청어', '화살꼴뚜기']
    df_filter = updated_df[updated_df['수산물표준코드명'].isin(target_fish)].copy()

    fish_map = {
        '대문어': '문어',
        '기름가자미': '가자미', '참가자미': '가자미', '홍가자미': '가자미', '가자미류': '가자미',
        '대구류': '대구',
        '곰치': '곰치_꼼치', '꼼치': '곰치_꼼치',
        '홍게': '붉은대게'
    }
    df_filter['수산물표준코드명'] = df_filter['수산물표준코드명'].replace(fish_map)

    # 동일 일자/수협/어종 가중평균 병합
    df_grouped = df_filter.groupby(['위판일자', '산지조합명', '수산물표준코드명'], as_index=False)[['위판중량', '위판금액']].sum()
    df_grouped['단가'] = df_grouped['위판금액'] / df_grouped['위판중량']
    df_filter = df_grouped.sort_values(['위판일자', '산지조합명', '수산물표준코드명']).reset_index(drop=True)

    df_filter.to_csv('data3_historical_master.csv', index=False, encoding='utf-8-sig')
    print("통합 마스터 데이터 업데이트 완료")
    return 1