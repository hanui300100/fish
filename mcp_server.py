import os
import glob
import json
import re
import requests
import sys  # 🌟 통신 방해 없이 로그를 남기기 위해 필수
from mcp.server.fastmcp import FastMCP

# MCP 서버 인스턴스 생성
mcp = FastMCP("DonghaeFishPredictor")

# 🌟 [핵심 수정] 이 파일(mcp_server.py)이 있는 진짜 폴더 위치를 무조건 찾아내서,
# 그 안에 있는 'daily_cache' 폴더를 절대 경로로 지정합니다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "daily_cache")

# ==========================================
# 🛠️ 내부 함수: JSON 파일 읽어오기
# ==========================================
def _get_latest_data():
    if not os.path.exists(CACHE_DIR):
        return None, None

    list_of_files = glob.glob(os.path.join(CACHE_DIR, 'market_data_*.json'))
    if not list_of_files:
        return None, None

    latest_file = max(list_of_files, key=os.path.getctime)

    date_match = re.search(r'market_data_(\d{8})\.json', latest_file)
    data_date = date_match.group(1) if date_match else "알 수 없음"

    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data, data_date
    except json.JSONDecodeError:
        print("⚠️ JSON 파일을 읽는 도중 디코딩 에러 발생", file=sys.stderr)
        return None, None
    except Exception as e:
        print(f"⚠️ 파일 읽기 실패: {e}", file=sys.stderr)
        return None, None


# ==========================================
# 🤖 도구 1: 전체 수산물 조회
# ==========================================
@mcp.tool()
def get_all_fish_predictions() -> str:
    """동해안 13종 수산물의 전체 최신 예측 단가 및 최근 7일 데이터를 가져옵니다."""
    data, data_date = _get_latest_data()
    if data is None:
        return "오류: 아직 AI 예측 데이터가 준비되지 않았습니다."

    response_payload = {
        "metadata": {"data_reference_date": data_date},
        "market_data": data
    }
    return json.dumps(response_payload, ensure_ascii=False, indent=2)


# ==========================================
# 🤖 도구 2: 특정 수산물 단일 조회
# ==========================================
@mcp.tool()
def get_specific_fish_prediction(fish_name: str) -> str:
    """특정 수산물의 AI 예측 단가와 조합별 변동률만 골라서 가져옵니다."""
    data, data_date = _get_latest_data()
    if data is None:
        return "오류: AI 예측 데이터 캐시가 존재하지 않습니다."

    if fish_name not in data:
        available = ", ".join(data.keys())
        return f"오류: '{fish_name}'에 대한 데이터가 없습니다. 현재 조회 가능한 수산물은 다음과 같습니다: [{available}]"

    response_payload = {
        "metadata": {"data_reference_date": data_date, "requested_fish": fish_name},
        "data": data[fish_name]
    }
    return json.dumps(response_payload, ensure_ascii=False, indent=2)


# ==========================================
# 🤖 도구 3: 강제 수동 업데이트
# ==========================================
@mcp.tool()
def force_market_data_update() -> str:
    """
    데이터가 너무 오래되었거나(어제 이전 데이터), 사용자가 "최신 데이터로 다시 분석해줘"라고 요구할 때
    FastAPI 서버에 강제 업데이트를 요청하는 도구입니다.
    """
    try:
        # 🌟 print 대신 sys.stderr.write 사용으로 통신 에러 방지
        print("🤖 LLM이 강제 업데이트를 요청했습니다.", file=sys.stderr)

        response = requests.get("http://127.0.0.1:8000/force-update", timeout=120)

        if response.status_code == 200:
            return "✅ [성공] 서버의 데이터가 지금 방금 최신화되었습니다. 'get_all_fish_predictions' 도구를 다시 호출해서 최신 데이터를 확인하세요."
        else:
            return f"❌ [실패] 서버 업데이트 중 오류가 발생했습니다. (HTTP {response.status_code})"

    except requests.exceptions.Timeout:
        return "⏳ 업데이트가 진행 중이지만 시간이 오래 걸리고 있습니다. 1분 뒤에 다시 데이터를 조회해 보세요."
    except Exception as e:
        return f"❌ 업데이트 요청 중 치명적 에러 발생: {e}"


# ==========================================
# 서버 실행부
# ==========================================
if __name__ == "__main__":
    mcp.run()