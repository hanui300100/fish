# %%
import requests
import xml.etree.ElementTree as ET
import pandas as pd
import time
import os
from datetime import datetime, timedelta
import concurrent.futures

# 💡 난수(Seed) 고정을 위한 라이브러리 추가
import numpy as np
import tensorflow as tf

# 딥러닝 및 전처리 라이브러리
from sklearn.preprocessing import LabelEncoder, StandardScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, Input
from tensorflow.keras.callbacks import EarlyStopping

# ==========================================
# 0. AI 일관성 유지 (시드 고정)
# ==========================================
# 코드를 다시 돌려도 똑같은 예측 결과가 나오도록 랜덤성을 통제합니다.
np.random.seed(42)
tf.random.set_seed(42)

# ==========================================
# 1. 시스템 설정 및 마스터 딕셔너리
# ==========================================
API_KEY = 'ef6d0601ed655d9cd98915b9cfb819bc3df7010dc1ad4568f85417725ad7f15c'
URL = 'http://apis.data.go.kr/1192000/select0040List/getselect0040List'
MASTER_FILE = 'donghae_master_data.csv'

TARGET_COOPS = [
    '강원고성군수산업협동조합', '죽왕수산업협동조합', '속초시수산업협동조합',
    '양양수산업협동조합', '강릉시수산업협동조합', '동해시수산업협동조합',
    '삼척수산업협동조합', '원덕수산업협동조합', '죽변수산업협동조합',
    '후포수산업협동조합', '영덕북부수산업협동조합', '강구수산업협동조합',
    '포항수산업협동조합', '구룡포수산업협동조합'
]

FISH_GROUPS = {
    '문어류': ['문어', '대문어', '피문어', '참문어', '돌문어', '발문어'],
    '가자미류': ['가자미', '가자미류', '기름가자미', '참가자미', '홍가자미', '물가자미', '용가자미', '찰가자미'],
    '대구류': ['대구', '대구류'],
    '아귀': ['아귀'],
    '넙치': ['넙치'],
    '대게': ['대게'],
    '붉은대게_홍게': ['붉은대게', '홍게'],
    '골뱅이': ['골뱅이'],
    '살오징어': ['살오징어'],
    '방어': ['방어'],
    '청어': ['청어'],
    '화살꼴뚜기': ['화살꼴뚜기'],
    '우렁쉥이': ['우렁쉥이', '멍게'],
    '해삼': ['해삼']
}

# ==========================================
# 2. 단일 API 요청 함수 (멀티스레딩용)
# ==========================================
def fetch_single_request(req_info):
    params = req_info['params']
    try:
        response = requests.get(URL, params=params, timeout=10)

        if any(error in response.text for error in ["quota exceeded", "LIMITED NUMBER", "Forbidden", "Unauthorized"]):
            return {"status": "QUOTA_ERROR", "data": []}

        if response.status_code == 200:
            root = ET.fromstring(response.content)
            items = root.findall('.//item')

            result_list = []
            for item in items:
                result_list.append({
                    "날짜": req_info['current_date'],
                    "월": int(req_info['current_date'][4:6]),
                    "조합": params['mxtrNm'],
                    "통합어종": req_info['group_name'],
                    "중량": float(item.findtext('csmtWt', 0)),
                    "단가": int(item.findtext('csmtUntpc', 0))
                })
            return {"status": "SUCCESS", "data": result_list}
    except Exception:
        pass
    return {"status": "ERROR", "data": []}

# ==========================================
# 3. 하이브리드 데이터 매니저 (CSV + 최신 API 터보 보충)
# ==========================================
def update_and_load_master_data():
    end_date = datetime.now()
    df_master = pd.DataFrame()

    if os.path.exists(MASTER_FILE):
        df_master = pd.read_csv(MASTER_FILE)
        df_master['날짜'] = df_master['날짜'].astype(str)
        last_saved_date = df_master['날짜'].max()
        start_date = datetime.strptime(last_saved_date, "%Y%m%d") + timedelta(days=1)
        print(f"📁 [로컬 DB] 기존 마스터 데이터 {len(df_master):,}건 로드 완료 (최종 업데이트: {last_saved_date})")
    else:
        print("❌ 마스터 파일(donghae_master_data.csv)이 없습니다. 파일을 같은 폴더에 넣어주세요.")
        return df_master

    if start_date.date() <= end_date.date():
        date_list = pd.date_range(start=start_date, end=end_date).strftime("%Y%m%d").tolist()
        print(f"🌐 [API 통신] 비어있는 {len(date_list)}일 치 최신 데이터를 터보 엔진으로 수집합니다...")

        quota_error = False

        for current_date in date_list:
            if quota_error: break

            requests_to_make = []
            for group_name, sub_fishes in FISH_GROUPS.items():
                for coop in TARGET_COOPS:
                    for fish in sub_fishes:
                        requests_to_make.append({
                            'current_date': current_date, 'group_name': group_name,
                            'params': {
                                'serviceKey': API_KEY, 'numOfRows': '100', 'pageNo': '1', 'type': 'xml',
                                'baseDt': current_date, 'mxtrNm': coop, 'mprcStdCodeNm': fish
                            }
                        })

            daily_data = []
            print(f"📅 {current_date} 수집 중 (일꾼 10명 투입)...", end=" ", flush=True)

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                results = executor.map(fetch_single_request, requests_to_make)
                for res in results:
                    if res['status'] == "QUOTA_ERROR":
                        quota_error = True
                        break
                    if res['status'] == "SUCCESS" and res['data']:
                        daily_data.extend(res['data'])

            if daily_data:
                df_daily = pd.DataFrame(daily_data)
                df_daily.to_csv(MASTER_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')
                print(f"({len(daily_data)}건 보충 완료!)")
            elif not quota_error:
                print("(데이터 없음)")

            if quota_error:
                print("\n🚨 [긴급 알림] API 트래픽 한계 도달! 오늘 모은 곳까지만 저장하고 AI 분석으로 넘어갑니다.")
                break

        df_master = pd.read_csv(MASTER_FILE)
        df_master['날짜'] = df_master['날짜'].astype(str)
        print(f"✨ [DB 최신화 완료] 현재 총 데이터 수: {len(df_master):,}건")
    else:
        print("✨ [최신 상태] 로컬 DB가 이미 오늘 날짜까지 완벽히 최신화되어 있습니다.")

    return df_master

# ==========================================
# 4. 딥러닝(Deep Learning) 신경망 예측 엔진
# ==========================================
def run_deep_learning_analysis(df_master, group_name):
    df = df_master[df_master['통합어종'] == group_name].copy()

    if df.empty or len(df) < 10:
        print(f"\n[알림] {group_name} 데이터가 부족하여 분석을 건너뜁니다.")
        return

    print(f"\n>>> 🧠 [{group_name} 인공신경망] 가중치 학습 시작 (데이터 {len(df):,}건)...")

    # 1. 데이터 인코딩 및 분리
    le_coop = LabelEncoder()
    df['조합_idx'] = le_coop.fit_transform(df['조합'])
    X = df[['중량', '월', '조합_idx']]
    y = df['단가']

    # 2. 정규화
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 3. 딥러닝 아키텍처
    model = Sequential([
        Input(shape=(X_scaled.shape[1],)),
        Dense(64, activation='relu'),
        Dropout(0.2),
        Dense(32, activation='relu'),
        Dense(16, activation='relu'),
        Dense(1)
    ])

    model.compile(optimizer='adam', loss='mean_squared_error', metrics=['mae'])
    early_stop = EarlyStopping(monitor='loss', patience=10, restore_best_weights=True)

    # 4. AI 학습 진행
    model.fit(X_scaled, y, epochs=100, batch_size=32, verbose=0, callbacks=[early_stop])

    # 5. 예측 및 현실적인 변동률(최근 30일 기준) 분석 💡
    current_month = datetime.now().month
    top_coop_idx = df['조합_idx'].mode()[0]
    top_coop_name = le_coop.inverse_transform([top_coop_idx])[0]
    avg_weight = df['중량'].mean()

    # 💡 최근 30일 데이터의 평균 단가만 추출하여 기준점 세팅
    last_month_str = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    recent_data = df[df['날짜'] >= last_month_str]

    if not recent_data.empty:
        recent_avg_price = recent_data['단가'].mean()
    else:
        recent_avg_price = df['단가'].mean() # 30일 데이터가 없으면 전체 평균 사용

    # 예측용 데이터 투입
    input_df = pd.DataFrame([[avg_weight, current_month, top_coop_idx]], columns=['중량', '월', '조합_idx'])
    input_scaled = scaler.transform(input_df)
    pred_price = model.predict(input_scaled, verbose=0)[0][0]

    # 변동률 계산
    fluctuation_rate = ((pred_price - recent_avg_price) / recent_avg_price) * 100

    if fluctuation_rate > 0:
        trend_symbol, trend_text = "▲", f"+{fluctuation_rate:.1f}% (상승 예측)"
    elif fluctuation_rate < 0:
        trend_symbol, trend_text = "▼", f"{fluctuation_rate:.1f}% (하락 예측)"
    else:
        trend_symbol, trend_text = "-", "0.0% (보합)"
    # 💡 [추가된 부분] 실제 최근 데이터(오늘/마지막 수집일) 기준 실제가 및 오차 계산
    latest_date_str = df['날짜'].max()  # 데이터에 있는 가장 마지막 날짜
    latest_data = df[df['날짜'] == latest_date_str]

    if not latest_data.empty:
        actual_price = latest_data['단가'].mean()
        error_value = pred_price - actual_price
        error_rate = (abs(error_value) / actual_price) * 100

        # 날짜 포맷 예쁘게 변경 (예: 20240510 -> 2024-05-10)
        formatted_date = f"{latest_date_str[:4]}-{latest_date_str[4:6]}-{latest_date_str[6:]}"
        actual_str = f"{int(actual_price):>10,d} 원 ({formatted_date} 기준)"

        if error_value > 0:
            error_str = f"+{int(error_value):,d} 원 (실제보다 {error_rate:.1f}% 높게 예측)"
        elif error_value < 0:
            error_str = f"{int(error_value):,d} 원 (실제보다 {error_rate:.1f}% 낮게 예측)"
        else:
            error_str = "0 원 (완벽히 일치!)"
    else:
        actual_str = "최근 데이터 없음"
        error_str = "계산 불가"

    # ==========================================
    # 화면 출력부 (프린트문)
    # ==========================================
    print("=" * 65)
    print(f"🤖 {group_name} 대분류 - 딥러닝 AI 단가 및 시장 변동률 분석")
    print("-" * 65)
    print(f"* 최다 거래소: {top_coop_name}")
    print(f"* 기준 중량  : 그룹 평균 {avg_weight:.1f}kg")
    print(f"* 최근(30일) 평균가 : {int(recent_avg_price):>10,d} 원")
    print(f"  ▶ 실제 최근 거래가: {actual_str}")
    print(f"  ▶ AI 예측가       : {int(pred_price):>10,d} 원")
    print(f"  ▶ AI 예측 오차    : {error_str}")
    print(f"  ▶ 단가 변동 추이  : {trend_symbol} {trend_text}")
    print("=" * 65)

    # 💡 6. 메모리 초기화 (텐서플로우 빨간 경고문 제거)
    tf.keras.backend.clear_session()

# ==========================================
# 5. 파이프라인 관제탑 (실행부)
# ==========================================
if __name__ == "__main__":
    print("==================================================")
    print("🚀 동해안 AI 수산물 단가 예측 하이브리드 파이프라인")
    print("==================================================")

    # 1. 데이터베이스 자동 최신화
    df_master_database = update_and_load_master_data()

    # 2. 딥러닝 분석 실행
    if not df_master_database.empty:
        # 분석을 원하는 어종 세팅
        RUN_TARGETS = ['붉은대게_홍게', '골뱅이', '살오징어', '방어', '청어', '화살꼴뚜기', '우렁쉥이', '해삼']

        for target_group in RUN_TARGETS:
            run_deep_learning_analysis(df_master_database, target_group)
    else:
        print("\n❌ 분석할 데이터가 없어 프로그램을 종료합니다.")
# %%
