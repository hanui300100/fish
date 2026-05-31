from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler  # 🔥 [추가] 백그라운드 스케줄러
import pandas as pd
import os
import glob
import json
from datetime import datetime

import update_fish_data
import update_weather_data
import split_fish_data
import make_daily_price
import evaluate_fish_model
import predict_1days

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED_FISH = ['문어', '가자미', '넙치', '대게', '대구', '아귀', '골뱅이', '방어', '살오징어', '곰치_꼼치', '붉은대게', '청어', '화살꼴뚜기']
CACHE_DIR = "daily_cache"


# ==========================================
# 🔥 [핵심 로직] 데이터 수집, 학습, 파일 저장 및 어제 파일 삭제 통합 함수
# ==========================================
def compute_and_cache_market_data():
    today_str = datetime.now().strftime("%Y%m%d")
    os.makedirs(CACHE_DIR, exist_ok=True)
    today_cache_file = os.path.join(CACHE_DIR, f"market_data_{today_str}.json")

    print(f"\n⏰ [배치 엔진] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - 전처리 및 AI 연산을 시작합니다.")

    # 1. 과거(어제 이전) 캐시 파일 자동 청소
    for file_path in glob.glob(os.path.join(CACHE_DIR, "market_data_*.json")):
        if file_path != today_cache_file:
            try:
                os.remove(file_path)
                print(f"🗑️ [서버 캐시 정리] 과거 데이터 삭제 완료: {file_path}")
            except Exception as e:
                print(f"❌ [서버 캐시 정리] 파일 삭제 실패: {e}")

    initialized_data = {}

    # 2. 데이터 최신화 및 어종 분리
    try:
        update_fish_data.update_fish_data()
        update_weather_data.update_weather_data()
        split_fish_data.split_fish_data()
        print('✅ 마스터 데이터 최신화 및 어종 파일 분리 완료')
    except Exception as e:
        print(f'🚨 수집 및 분리 단계 에러 발생: {e}')

    # 원시 지점 데이터 로드
    try:
        raw_data3 = pd.read_csv('data3_historical_master.csv', encoding='utf-8')
    except UnicodeDecodeError:
        raw_data3 = pd.read_csv('data3_historical_master.csv', encoding='cp949')

    raw_data3['위판일자'] = pd.to_datetime(raw_data3['위판일자'])

    # 3. 13종 어종을 순회하며 예측 가공
    for fish in SUPPORTED_FISH:
        try:
            make_daily_price.make_daily_price(fish)
            result_model = evaluate_fish_model.evaluate_fish_model(fish)
            pred_df = predict_1days.predict_1days(result_model)
            tomorrow_pred = pred_df['예측단가'].iloc[0]

            df = pd.read_csv(f'fish_daily/{fish}.csv')
            recent_avg = df.tail(30)['단가'].mean()

            recent_7_days_list = [
                {"date": str(row['위판일자']).split(' ')[0], "price": str(int(row['단가']))}
                for _, row in df.tail(7).iterrows()
            ]

            fish_data3 = raw_data3[raw_data3['수산물표준코드명'] == fish].sort_values('위판일자')
            branches = fish_data3['산지조합명'].unique()
            branch_info_list = []

            for branch in branches:
                b_df = fish_data3[fish_data3['산지조합명'] == branch]
                if len(b_df) == 0: continue

                b_avg = b_df['단가'].mean()
                b_recent_7 = b_df.tail(7)
                b_7d_list = [
                    {"date": str(r['위판일자']).split(' ')[0], "price": str(int(r['단가']))}
                    for _, r in b_recent_7.iterrows()
                ]

                if len(b_recent_7) >= 2:
                    latest = b_recent_7.iloc[-1]['단가']
                    prev = b_recent_7.iloc[-2]['단가']
                    trend = "up" if latest > prev else ("down" if latest < prev else "none")
                    change_pct = int(abs(latest - prev) / prev * 100) if prev != 0 else 0
                else:
                    trend = "none"
                    change_pct = 0

                branch_info_list.append({
                    "branch_name": str(branch),
                    "avg_price": str(int(b_avg)),
                    "trend": trend,
                    "change": f"{change_pct}%",
                    "recent_7_days": b_7d_list
                })

            initialized_data[fish] = {
                "recent_avg_price": str(int(recent_avg)),
                "predicted_price": str(int(tomorrow_pred)),
                "recent_7_days": recent_7_days_list,
                "branches": branch_info_list
            }

        except Exception as e:
            print(f"❌ {fish} 가공 중 에러 발생: {e}")
            initialized_data[fish] = {
                "recent_avg_price": "0",
                "predicted_price": "0",
                "recent_7_days": [],
                "branches": []
            }

    # 4. JSON 캐시 파일로 저장
    with open(today_cache_file, 'w', encoding='utf-8') as f:
        json.dump(initialized_data, f, ensure_ascii=False, indent=4)

    print(f"💾 오늘의 마켓 데이터 캐시 파일 백업 완료: {today_cache_file}")
    return initialized_data


# ==========================================
# 🔥 [자동 예약 시스템] 매일 새벽 03:00에 함수 강제 실행 설정
# ==========================================
scheduler = BackgroundScheduler()
# cron 방식을 사용하여 매일 hour=3, minute=0 이 되면 시스템 시계가 이를 감지하여 함수를 실행합니다.
scheduler.add_job(compute_and_cache_market_data, 'cron', hour=3, minute=0)
scheduler.start()


# ==========================================
# 🚀 [플러터 연동 엔드포인트] 접속 시 처리망 (폴백 시스템 적용)
# ==========================================
@app.get("/initialize")
def initialize_market_data():
    today_str = datetime.now().strftime("%Y%m%d")
    today_cache_file = os.path.join(CACHE_DIR, f"market_data_{today_str}.json")

    # 망 분리 1단계: 오늘 자 새벽 3시에 만들어둔 파일이 존재하면 0.1초 만에 그대로 리턴!
    if os.path.exists(today_cache_file):
        print(f"✅ [캐시 서빙] 오늘 자 예측 데이터가 확인되어 즉시 전송합니다.")
        with open(today_cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    # 망 분리 2단계 (Fallback): 만약 새벽 3시에 컴퓨터가 꺼져있었거나 에러로 인해 파일이 없다면?
    # 🌟 유저가 접속한 순간 비상 정지망이 가동되어 실시간으로 모델을 직접 돌려 파일을 생성하고 리턴합니다!
    print(f"⚠️ [비상 폴백 가동] 오늘 자 예측 파일이 없습니다! 실시간 AI 연산을 즉시 시작합니다...")
    data = compute_and_cache_market_data()
    return data

# ==========================================
# 🚨 [LLM/관리자용 비상 스위치] 강제 수동 업데이트 엔드포인트
# ==========================================
@app.get("/force-update")
def force_update():
    print("⚠️ [수동 업데이트 요청 수신] LLM 또는 관리자의 요청으로 실시간 데이터 수집 및 AI 연산을 강제로 시작합니다!")
    try:
        # 기존에 만들어둔 통합 연산 함수를 그대로 재활용합니다.
        compute_and_cache_market_data()
        return {"status": "success", "message": "모든 수산물 데이터의 강제 최신화가 완료되었습니다."}
    except Exception as e:
        return {"status": "error", "message": str(e)}