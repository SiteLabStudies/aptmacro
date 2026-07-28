"""
GitHub Actions에서 매달 실행되는 자동 게시 스크립트.

로직: 저장소 안에 이미 있는 '{연도}년 {월}월.html' 파일들 중 가장 최신 달의
"다음 달"을 REB API로 조회한다. 아직 REB가 그 달을 공표하지 않았으면
(REB는 KB보다 한 달가량 공표가 늦다) 조용히 종료한다 — 다음 달 스케줄 실행 때
다시 시도되므로 실패로 취급하지 않는다.

REB_API_KEY는 GitHub Actions Secrets에서 환경변수로 주입된다.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reb_extract import load_prices_with_prev  # noqa: E402
from generate_monthly_html import apply_monthly_prices_v2  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
AUTOMATION_DIR = Path(__file__).resolve().parent

FILENAME_RE = re.compile(r"^(\d{4})년 (\d{1,2})월\.html$")


def find_latest_published_month() -> tuple:
    latest = None
    for f in REPO_ROOT.glob("*년 *월.html"):
        m = FILENAME_RE.match(f.name)
        if not m:
            continue
        ym = (int(m.group(1)), int(m.group(2)))
        if latest is None or ym > latest:
            latest = ym
    if latest is None:
        raise SystemExit("기존 월별 파일을 하나도 못 찾음 — 저장소 구조 확인 필요")
    return latest


def next_month(year: int, month: int) -> tuple:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def insert_dropdown_entry(index_html_path: Path, year: int, month: int) -> None:
    html = index_html_path.read_text(encoding="utf-8")
    marker = '<div class="dropdown-content">'
    idx = html.find(marker)
    if idx == -1:
        raise SystemExit("index.html에서 dropdown-content를 못 찾음")
    insert_at = idx + len(marker)
    entry = (
        f'\n<!--{year}년 {month}월-->\n'
        f'<a href="https://sitelabstudies.github.io/aptmacro/{year}년 {month}월.html">'
        f'<div class="Date" onclick="showMenu(this.innerText)">{year}년 {month}월</div></a>'
    )
    new_html = html[:insert_at] + entry + html[insert_at:]
    index_html_path.write_text(new_html, encoding="utf-8")


def main():
    latest_year, latest_month = find_latest_published_month()
    target_year, target_month = next_month(latest_year, latest_month)
    print(f"저장소 최신월: {latest_year}.{latest_month} -> 목표월: {target_year}.{target_month}")

    try:
        prices, prev_prices, missing = load_prices_with_prev(target_year, target_month)
    except ValueError as e:
        print(f"REB 미공표로 판단, 이번 실행은 건너뜀: {e}")
        return

    if not prices:
        print("REB 응답에 지역 데이터가 없음, 이번 실행은 건너뜀")
        return

    if missing:
        print(f"경고: {len(missing)}개 지역 매핑 실패 - {missing}")

    template_html = (AUTOMATION_DIR / "map_template.html").read_text(encoding="utf-8")
    period_label = f"{target_year}년 {target_month}월"
    new_html, unmatched = apply_monthly_prices_v2(template_html, prices, prev_prices, period_label)
    if unmatched:
        print(f"경고: 치환 실패 {len(unmatched)}개 - {unmatched}")

    out_path = REPO_ROOT / f"{target_year}년 {target_month}월.html"
    out_path.write_text(new_html, encoding="utf-8")
    print(f"생성: {out_path.name}")

    insert_dropdown_entry(REPO_ROOT / "index.html", target_year, target_month)
    print("index.html 드롭다운 갱신 완료")


if __name__ == "__main__":
    main()
