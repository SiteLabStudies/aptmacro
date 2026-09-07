"""주간 워크플로우 프리플라이트 — REB_API_KEY가 살아 있는지 매주 확인한다.

왜 필요한가:
  publish_next_month.py는 "다음 달"을 조회하는데, REB가 아직 그 달을 공표하지 않았으면
  키가 있든 없든 똑같이 "미공표"로 조용히 끝난다(정상 동작). 그래서 **공표할 새 달이 없는
  주에는 키가 죽어 있어도 워크플로우가 초록불**이고, 문제가 몇 주씩 숨는다.
  실제로 2026-08-24에 새 달이 공표된 그 한 주에만 사고가 드러났다.

그래서 여기서는 **이미 공표된 달**(저장소에 마지막으로 게시된 달)을 조회해
71개 지역이 전부 오는지 본다. 키가 없거나 잘못되면 그 주에 바로 빨간불이 뜬다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reb_extract import load_prices_by_var, CLS_ID_BY_VAR  # noqa: E402
from publish_next_month import find_latest_published_month  # noqa: E402

EXPECTED = len(CLS_ID_BY_VAR)


def main():
    year, month = find_latest_published_month()
    print(f"프리플라이트: 이미 게시된 {year}.{month} 자료로 REB 응답을 점검합니다")

    try:
        prices, missing = load_prices_by_var(year, month)
    except ValueError as e:
        print(f"::error::REB 조회 실패: {e}")
        raise SystemExit(1)

    if len(prices) != EXPECTED or missing:
        print(f"::error::지역 {len(prices)}/{EXPECTED}개만 조회됐습니다 (누락 {len(missing)}개: {missing[:5]}…).")
        print("::error::REB_API_KEY가 없거나 잘못됐을 때 나타나는 증상입니다. "
              "무인증 모드는 5개 행만 반환하며, 그중 우리 지역과 겹치는 것은 종로구뿐입니다.")
        print("::error::저장소 Settings > Secrets and variables > Actions 에서 REB_API_KEY를 확인하세요.")
        raise SystemExit(1)

    print(f"정상: {len(prices)}/{EXPECTED}개 지역 조회됨 — 인증키 유효")


if __name__ == "__main__":
    main()
