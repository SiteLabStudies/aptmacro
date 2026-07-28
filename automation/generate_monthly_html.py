"""
기존 index.html(폴리곤 좌표 포함, 고정)을 템플릿으로 삼아
지역별 fillColor / 가격 텍스트만 이번 달 값으로 치환해 새 월별 HTML을 생성한다.

전제(파이프라인_로직분석.md 참고):
- 폴리곤 좌표(paths)는 매달 바뀌지 않는다 -> 통째로 재생성할 필요 없음
- 지역별로 바뀌는 것은 fillColor 하나, 그리고 InfoWindow 안의 "...만원<br>" 가격 텍스트 하나뿐

사용법: monthly_prices 딕셔너리(var_name -> ㎡당 원자료)를 채우고 실행
"""
import re
from pathlib import Path

from apt_price_logic import compute_row
from district_labels import LABEL_BY_VAR

BLOCK_RE = re.compile(
    r'var (?P<var>\w+) = new google\.maps\.Polygon\(\{paths: (?P<path>\w+),'
    r'(?P<pre>[^}]*?fillColor: ")(?P<color>#[0-9A-Fa-f]{6})(?P<post1>".*?function (?P<func>Dobi\d+)\(event\) \{'
    r'let contentString ="<font size=3\.5><b>(?P<label>[^<]+)</b>.*?\+")'
    r'(?P<price>\d[\d.]*)(?P<post2>만원<br>")'
)


def apply_monthly_prices(template_html: str, prices_by_var: dict) -> tuple[str, list[str]]:
    """prices_by_var: {var_name: price_per_sqm (환산 전, ㎡당 원자료)}
    반환: (치환된 HTML, 매핑에 없어서 못 바꾼 var_name 리스트)
    """
    missing = []

    def _replace(m: re.Match) -> str:
        var = m.group("var")
        if var not in prices_by_var:
            missing.append(var)
            return m.group(0)
        row = compute_row(prices_by_var[var])
        return (
            f'var {var} = new google.maps.Polygon({{paths: {m.group("path")},'
            f'{m.group("pre")}{row["color"]}{m.group("post1")}'
            f'{row["price_per_pyeong"]}{m.group("post2")}'
        )

    new_html = BLOCK_RE.sub(_replace, template_html)
    return new_html, missing


def list_template_districts(template_html: str) -> list[dict]:
    """템플릿에 있는 지역(var_name) 목록과 현재 값을 추출 (매핑 파일 준비용)"""
    out = []
    for m in BLOCK_RE.finditer(template_html):
        out.append({
            "var": m.group("var"),
            "path": m.group("path"),
            "label": m.group("label").strip(),
            "current_color": m.group("color"),
            "current_price_pyeong": m.group("price"),
        })
    return out


# ---------------------------------------------------------------------------
# v2: 개선된 디자인(폴리곤 hover 효과 + 정보창 카드형 UI, 전월대비 배지)
# 2026-07-11 시안 승인 후 적용. v1(BLOCK_RE)은 마이그레이션 시 원본을 읽는 용도로만 남겨둠.
# ---------------------------------------------------------------------------

BLOCK_RE_V2 = re.compile(
    r'var (?P<var>\w+) = new google\.maps\.Polygon\(\{paths: (?P<path>\w+),'
    r'.*?function (?P<func>Dobi\d+)\(event\) \{.*?\}',
    re.S,
)


def _format_price(v: float) -> str:
    return f"{v:,.1f}"


def _badge_html(pct_change) -> str:
    if pct_change is None:
        return ""
    if pct_change > 0:
        arrow, bg, fg = "▲", "#e8f5e9", "#2e7d32"
    elif pct_change < 0:
        arrow, bg, fg = "▼", "#fdecea", "#c62828"
    else:
        arrow, bg, fg = "-", "#f5f5f5", "#666666"
    pct_str = f"{abs(pct_change):.1f}"
    return (
        "<div style='display:flex;align-items:center;gap:4px'>"
        f"<span style='background:{bg};color:{fg};font-size:12px;font-weight:600;padding:2px 6px;border-radius:6px'>{arrow} {pct_str}%</span>"
        "<span style='font-size:12px;color:#999'>전월 대비</span>"
        "</div>"
    )


def build_block_v2(var: str, path: str, func: str, label: str, color: str,
                    price_per_pyeong: float, pct_change, period_label: str) -> str:
    """지역 하나의 폴리곤+정보창 JS 블록을 새 디자인으로 통째로 생성한다.
    2026-07-11: Google InfoWindow 기본 패딩과 중복되던 우리 div의 padding을 0으로 제거(세로는 그 상태 유지).
    닫기 'x' 버튼이 공간을 차지해 줄바꿈이 생긴다는 피드백 -> index.html <head>에 닫기버튼 50% 축소 CSS를
    추가(migrate_template.py)함. 너비는 각 줄을 개별로 격리해 실측한 결과(가장 긴 줄 "12,345.6만원"
    기준 줄바꿈 없는 최소 127px)에 닫기버튼 침범분 여유(약 11px)를 더해 138px로 설정."""
    badge = _badge_html(pct_change)
    content = (
        "<div style='padding:0;width:138px;font-family:sans-serif'>"
        f"<div style='display:flex;align-items:center;gap:6px;margin-bottom:5px'><span style='width:12px;height:12px;border-radius:3px;background:{color};flex-shrink:0'></span><span style='font-size:16px;font-weight:600;color:#1a1a1a'>{label}</span></div>"
        "<div style='font-size:13px;color:#666;margin-bottom:2px'>아파트 평당 매매가격</div>"
        f"<div style='font-size:24px;font-weight:600;color:#1a1a1a;margin-bottom:4px'>{_format_price(price_per_pyeong)}<span style='font-size:14px;font-weight:400;color:#666'>만원</span></div>"
        f"{badge}"
        f"<div style='font-size:11px;color:#999;margin-top:5px;border-top:1px solid #eee;padding-top:4px'>{period_label} 기준</div>"
        "</div>"
    )
    return (
        f'var {var} = new google.maps.Polygon({{paths: {path},'
        f'strokeColor: "#ffffff",strokeOpacity: 0.6,strokeWeight: 1,fillColor: "{color}",fillOpacity: 0.85}});'
        f'{var}.setMap(map);'
        f'{var}.addListener("mouseover",function(){{this.setOptions({{strokeWeight: 2,strokeColor: "#333333",fillOpacity: 0.95}});}});'
        f'{var}.addListener("mouseout",function(){{this.setOptions({{strokeWeight: 1,strokeColor: "#ffffff",fillOpacity: 0.85}});}});'
        f'{var}.addListener("click",{func});'
        f'infoWindow = new google.maps.InfoWindow();'
        f'function {func}(event) {{let contentString ="{content}";'
        f'infoWindow.setContent(contentString);infoWindow.setPosition(event.latLng);infoWindow.open(map);}}'
    )


def apply_monthly_prices_v2(template_html: str, prices_by_var: dict, prev_prices_by_var: dict,
                             period_label: str) -> tuple[str, list[str]]:
    """v2 템플릿(마이그레이션 이후의 index.html)에 이번 달 값을 채운다.
    prices_by_var/prev_prices_by_var: {var_name: ㎡당 원자료(환산 전)}"""
    missing = []

    def _replace(m: re.Match) -> str:
        var, path, func = m.group("var"), m.group("path"), m.group("func")
        if var not in prices_by_var:
            missing.append(var)
            return m.group(0)
        row = compute_row(prices_by_var[var], prev_prices_by_var.get(var))
        label = LABEL_BY_VAR.get(var, var)
        return build_block_v2(var, path, func, label, row["color"], row["price_per_pyeong"],
                               row["pct_change"], period_label)

    new_html = BLOCK_RE_V2.sub(_replace, template_html)
    return new_html, missing


def list_template_districts_v2(template_html: str) -> list[dict]:
    return [
        {"var": m.group("var"), "path": m.group("path"), "func": m.group("func"),
         "label": LABEL_BY_VAR.get(m.group("var"), m.group("var"))}
        for m in BLOCK_RE_V2.finditer(template_html)
    ]


if __name__ == "__main__":
    template_path = Path(__file__).resolve().parent.parent / "index.html"
    html = template_path.read_text(encoding="utf-8")

    districts = list_template_districts(html)
    print(f"템플릿에서 {len(districts)}개 지역 추출됨. 예시:")
    for d in districts[:5]:
        print(" ", d)

    # 예시: 전부 동일값(테스트용)으로 치환 -> missing 없이 전부 바뀌는지만 확인
    fake_prices = {d["var"]: 1000.0 for d in districts}
    new_html, missing = apply_monthly_prices(html, fake_prices)
    print(f"치환 실패(매핑 누락) 지역 수: {len(missing)}")
    assert not missing, missing
    print("OK: 템플릿 치환 로직 정상 동작 확인")
