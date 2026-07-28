"""
매매데이터 코딩.xlsm 의 수식(데이터가공소 시트)을 그대로 이식한 계산 로직.
근거: 파이프라인_로직분석.md
"""

PYEONG_FACTOR = 3.305785  # 1평 = 3.305785 m^2

_COLOR_THRESHOLDS = [
    (3100, "#D7191C"), (3000, "#DC2E26"), (2900, "#E1422F"), (2800, "#E75739"),
    (2700, "#EC6B42"), (2600, "#F1804C"), (2500, "#F69455"), (2400, "#FCA95F"),
    (2300, "#FDB668"), (2200, "#FDC278"), (2100, "#FECD85"), (2000, "#FED892"),
    (1900, "#FEE39F"), (1800, "#FFEEAC"), (1700, "#FFF9B9"), (1600, "#F9FCC2"),
    (1500, "#EEF7C8"), (1400, "#E2F2CD"), (1300, "#D6EDD3"), (1200, "#CBE7D9"),
    (1100, "#BFE2DF"), (1000, "#B4DDE5"), (900, "#A7D6E7"), (800, "#95C9E0"),
    (700, "#84BCD9"), (600, "#72AFD2"), (500, "#61A2CB"), (400, "#4F95C4"),
    (300, "#3E88BD"),
]
_COLOR_BELOW_MIN = "#2C7BB6"


def to_pyeong_price(price_per_sqm: float) -> float:
    """C열 = A열 * $M$1"""
    return price_per_sqm * PYEONG_FACTOR


def truncate_1(value: float) -> float:
    """D열 = TRUNC(C열, 1) — 소수 둘째자리 이하 절삭(반올림 아님)"""
    return int(value * 10) / 10


def color_for_price(price_per_sqm: float) -> str:
    """B열 색상 매핑 사다리. 주의: A열(㎡당 원자료, 환산 전!) 기준으로 계단이 매겨짐.
    D열(평당가)이 아니라 A열 값을 그대로 넣어야 함 — 실 데이터로 검증 완료."""
    for threshold, color in _COLOR_THRESHOLDS:
        if price_per_sqm >= threshold:
            return color
    return _COLOR_BELOW_MIN


def compute_row(price_per_sqm: float, prev_price_per_sqm: float = None) -> dict:
    """A열(㎡당 원자료) 하나를 받아 D열(평당가), B열(색상)을 함께 반환.
    prev_price_per_sqm(전월 ㎡당 원자료)을 주면 전월 대비 등락률(pct_change)도 계산한다.
    등락률은 환산 전 값의 비율이라 평당/㎡당 어느 쪽으로 계산해도 결과가 같다."""
    pyeong_raw = to_pyeong_price(price_per_sqm)
    pyeong_price = truncate_1(pyeong_raw)
    row = {
        "price_per_sqm": price_per_sqm,
        "price_per_pyeong": pyeong_price,
        "color": color_for_price(price_per_sqm),
        "pct_change": None,
    }
    if prev_price_per_sqm:
        row["pct_change"] = round((price_per_sqm - prev_price_per_sqm) / prev_price_per_sqm * 100, 1)
    return row


if __name__ == "__main__":
    # 검증1: xlsm A1 = 669.8427655024941 -> 실제 B1=#72AFD2, D1=2214.3
    row1 = compute_row(669.8427655024941)
    assert row1["price_per_pyeong"] == 2214.3, row1
    assert row1["color"] == "#72AFD2", row1

    # 검증2: 라이브 index.html의 강남구 표시값(8582.5만원/평, fillColor #F69455)을
    # 역산한 ㎡당가(8582.5/3.305785=2596.2)로 재계산해 색상이 일치하는지 확인
    row2 = compute_row(8582.5 / PYEONG_FACTOR)
    assert row2["color"] == "#F69455", row2

    print("OK:", row1, row2)
