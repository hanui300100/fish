#전체 예측
import pandas as pd
import update_fish_data
import update_weather_data
import split_fish_data

from make_daily_price import make_daily_price
from evaluate_fish_model import evaluate_fish_model
from predict_7days import predict_7days

# =========================
# 전체 어종 예측 함수
# =========================


def predict_all_fish():
    update_fish_data()
    update_weather_data()
    split_fish_data(input_file='data3_historical_master.csv')  # 마스터 파일 지정

    # 🔥 [수정] 통합된 13종 전체 순회 리스트
    fish_list = ['문어', '가자미', '넙치', '대게', '대구', '아귀', '골뱅이', '방어', '살오징어', '곰치_꼼치', '붉은대게', '청어', '화살꼴뚜기']
    result_list = []

    for fish in fish_list:
        make_daily_price(fish)
        try:
            print(f'\n===== {fish} 예측 시작 =====')
            result = evaluate_fish_model(fish)  # 이 내부에 명절/결항 메커니즘이 그대로 유지됩니다.
            pred_df = predict_7days(result)
            pred_df = pred_df[['위판일자', '예측단가']].rename(columns={'예측단가': fish})
            result_list.append(pred_df)
            print(f'{fish} 예측 완료')
        except Exception as e:
            print(f'{fish} 에러:', e)

    if result_list:
        final_df = result_list[0]
        for df in result_list[1:]:
            final_df = pd.merge(final_df, df, on='위판일자', how='outer')

        final_df = final_df.sort_values('위판일자')
        print('\n전체 13종 예측 완료')
        print(final_df)
        return final_df


predict_all_fish()