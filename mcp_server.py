import os
import glob
import json
import re
import requests  # 🌟 [추가] FastAPI 서버에 요청을 보내기 위해 필요합니다.
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("DonghaeFishPredictor")
CACHE_DIR = "daily_cache"


# ... (기존 _get_latest_data, get_all_fish_predictions, get_specific_fish_prediction 코드는 그대로 유지) ...

# ==========================================
# 🤖 [신규 도구] LLM이 스스로 판단해서 누르는 수동 업데이트 버튼
# ==========================================
@mcp.tool()
def force_market_data_update() -> str:
    """
    데이터가 너무 오래되었거나(어제 이전 데이터), 사용자가 "최신 데이터로 다시 분석해줘"라고 요구할 때
    FastAPI 서버에 강제 업데이트를 요청하는 도구입니다.
    주의: 기상청 데이터 수집 및 13종 AI 재학습이 일어나므로 약 1~2분이 소요됩니다.
    """
    try:
        # 1. LLM이 행동을 시작함을 알림
        print("🤖 LLM이 데이터가 낡았다고 판단하여 강제 업데이트(force-update)를 요청했습니다.")

        # 2. FastAPI 서버의 8000번 포트 비상 스위치를 누름 (시간이 꽤 걸리므로 timeout을 넉넉히 120초로 줍니다)
        response = requests.get("http://127.0.0.1:8000/force-update", timeout=120)

        if response.status_code == 200:
            return "✅ [성공] 서버의 데이터가 지금 방금 최신화되었습니다. 'get_all_fish_predictions' 도구를 다시 호출해서 최신 데이터를 확인하세요."
        else:
            return f"❌ [실패] 서버 업데이트 중 오류가 발생했습니다. (HTTP {response.status_code})"

    except requests.exceptions.Timeout:
        return "⏳ 업데이트가 진행 중이지만 시간이 오래 걸리고 있습니다. 1분 뒤에 다시 데이터를 조회해 보세요."
    except Exception as e:
        return f"❌ 업데이트 요청 중 치명적 에러 발생: {e}"


if __name__ == "__main__":
    mcp.run()