#간단한 ui
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import evaluate_fish_model
import make_daily_price
import predict_7days
import split_fish_data
import update_fish_data
import update_weather_data

# =========================
# 메인 함수들
# =========================
# update_fish_data()
# split_fish_data()
# make_daily_price(fish_name)
# update_weather_data()
# evaluate_fish_model(fish_name)
# predict_7days(result)

# =========================
# UI 함수
# =========================

result_model = None


def log(msg):
    text_log.insert(tk.END, msg + '\n')
    text_log.see(tk.END)


def run_all():

    global result_model

    fish_name = fish_var.get()

    try:

        log('===== 데이터 최신화 시작 =====')

        update_fish_data.update_fish_data()
        log('수산물 데이터 최신화 완료')

        update_weather_data.update_weather_data()
        log('날씨 데이터 최신화 완료')

        log('===== 어종 분리 =====')

        split_fish_data.split_fish_data()

        log('===== 일별 데이터 생성 =====')

        make_daily_price.make_daily_price(fish_name)

        log(f'{fish_name} 일별 데이터 생성 완료')

        log('===== 모델 생성 =====')

        result_model = evaluate_fish_model.evaluate_fish_model(fish_name)

        log('모델 생성 완료')

        log('===== 7일 예측 =====')

        pred_df = predict_7days.predict_7days(result_model)

        log(pred_df.to_string())

        messagebox.showinfo(
            '완료',
            f'{fish_name} 예측 완료'
        )

    except Exception as e:

        log(f'에러 발생: {e}')

        messagebox.showerror(
            '에러',
            str(e)
        )


def start_thread():

    thread = threading.Thread(target=run_all)

    thread.start()


# =========================
# tkinter UI
# =========================

root = tk.Tk()

root.title('수산물 가격 예측 시스템')

root.geometry('700x600')

# 제목
title = tk.Label(
    root,
    text='수산물 가격 예측 시스템',
    font=('맑은 고딕', 18, 'bold')
)

title.pack(pady=10)

# 어종 선택
frame = tk.Frame(root)

frame.pack(pady=10)

label = tk.Label(
    frame,
    text='어종 선택:',
    font=('맑은 고딕', 12)
)

label.pack(side=tk.LEFT, padx=5)

fish_var = tk.StringVar()

fish_combo = ttk.Combobox(
    frame,
    textvariable=fish_var,
    state='readonly',
    width=20
)

fish_combo['values'] = (
    '문어', '가자미', '넙치', '대게', '대구', '아귀', '골뱅이', '방어', '살오징어', '곰치_꼼치', '붉은대게', '청어', '화살꼴뚜기'
)

fish_combo.current(0)

fish_combo.pack(side=tk.LEFT)

# 실행 버튼
run_button = tk.Button(
    root,
    text='예측 시작',
    font=('맑은 고딕', 12, 'bold'),
    bg='skyblue',
    command=start_thread
)

run_button.pack(pady=10)

# 로그창
text_log = tk.Text(
    root,
    height=25,
    width=85,
    font=('Consolas', 10)
)

text_log.pack(pady=10)

# 스크롤바
scrollbar = tk.Scrollbar(root)

scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

text_log.config(yscrollcommand=scrollbar.set)

scrollbar.config(command=text_log.yview)

root.mainloop()