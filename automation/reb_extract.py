"""
한국부동산원(REB) R-ONE 부동산통계정보 Open API에서
'(월) 평균단위매매가격_아파트'(㎡당, STATBL_ID=A_2024_00061)를 가져온다.

API 가이드: https://www.reb.or.kr/r-one/portal/openapi/openApiDevPage.do
엔드포인트: https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do

인증키(KEY)가 없으면 자동으로 'sample' 모드로 동작하며, 이 모드에서도
데이터 자체는 실제 값이 나오지만 페이지당 건수 등에 제한이 있을 수 있다
(2026-07-11 확인: KEY 생략 상태로 단일 지역 조회는 정상 동작 확인됨).
실 운영 시에는 REB_API_KEY 환경변수에 발급받은 키를 넣으면 된다.
(환경변수가 없으면 이 파일과 같은 폴더의 .env에서 REB_API_KEY=... 를 자동으로 읽는다.
.env는 절대 git에 커밋/푸시하지 말 것 — API 키가 그대로 노출된다.)
"""
import os
import time
import urllib.request
import urllib.parse
import json
from pathlib import Path


def _load_dotenv():
    if os.environ.get("REB_API_KEY"):
        return
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

ENDPOINT = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
STATBL_ID = "A_2024_00061"  # (월) 평균단위매매가격_아파트 (㎡당)
DTACYCLE_CD = "MM"
ITM_ID = "100001"  # 가격

# 수도권 71개 지도 var_name -> REB CLS_ID (지역코드)
# 서울 25개구 = 강북14개구+강남11개구, 경기 26개시, 인천 8개구(중구/서구는 여러 폴리곤 조각이 같은 코드 공유)
# 출처: https://www.reb.or.kr/r-one/portal/openapi/openApiGuideCdPage.do (통계표 A_2024_00061 지역코드)
CLS_ID_BY_VAR = {
    # 서울 강북14개구
    "Jongno_gu": 530011, "Joong_gu": 530012, "Yongsan_gu": 530013,
    "Seongdong_gu": 530015, "Gwangjin_gu": 530016, "Dongdaemun_gu": 530017,
    "Joongnang_gu": 530018, "Seongbuk_gu": 530019, "Gangbuk_gu": 530020,
    "Dobong_gu": 530021, "Nowon_gu": 530022, "Eunpyeong_gu": 530024,
    "Seodaemun_gu": 530025, "Mapo_gu": 530026,
    # 서울 강남11개구
    "Yangcheon_gu": 530029, "Gangseo_gu": 530030, "Guro_gu": 530031,
    "Geumcheon_gu": 530032, "Yeongdeungpo_gu": 530033, "Dongjak_gu": 530034,
    "Gwanak_gu": 530035, "Seocho_gu": 530037, "Gangnam_gu": 530038,
    "Songpa_gu": 530039, "Gangdong_gu": 530040,
    # 경기 26개시
    "Gwacheon_si": 520018, "Anyang_si": 520019, "Seongnam_si": 520020,
    "Gunpo_si": 520021, "Uiwang_si": 520022, "Anseong_si": 520024,
    "Yongin_si": 520025, "Suwon_si": 520026, "Bucheon_si": 520028,
    "Ansan_si": 520029, "Siheung_si": 520030, "Gwangmyeong_si": 520031,
    "Hwaseong_si": 520032, "Ohsan_si": 520033, "Pyeongtaek_si": 520034,
    "Namyangju_si": 520036, "Guri_si": 520037, "Hanam_si": 520038,
    "Gwangju_si": 520039, "Icheon_si": 520041, "Gimpo_si": 520044,
    "Goyang_si": 520045, "Paju_si": 520046, "Dongducheon_si": 520049,
    "Yangju_si": 520050, "Uijeongbu_si": 520051,
    # 인천 8개구 (분할 폴리곤은 같은 구 코드를 공유)
    "dong_gu": 510021, "michuhol_gu": 510023, "yeonsu_gu": 510024,
    "namdong_gu": 510025, "bupyeong_gu": 510026, "gyeyang_gu": 510027,
    **{f"jung{n:02d}_gu": 510020 for n in range(1, 11)},
    **{f"seo{n:02d}_gu": 510028 for n in range(1, 5)},
}


def _call(params: dict, retries: int = 3) -> dict:
    key = os.environ.get("REB_API_KEY")
    if key:
        params["KEY"] = key
    params.setdefault("Type", "json")
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (TimeoutError, OSError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 * attempt)  # REB 서버 일시적 응답 지연 대비 점증 대기
    raise last_err


def load_month_prices_by_cls_id(year: int, month: int, pSize: int = 300) -> dict:
    """해당 월의 {CLS_ID: 천원/㎡ 원자료} 전체를 받는다(지역코드 생략, 필요시 페이지네이션).
    주의: 인증키 없는 sample 모드는 요청 pSize와 무관하게 소수 건으로 제한된다
    (2026-07-11 확인: 10건). 전체 지역(약 234건, 전국+시도+수도권세부+시군구)을
    받으려면 REB_API_KEY 환경변수에 정식 발급 키를 설정해야 한다."""
    ym = f"{year:04d}{month:02d}"
    result = {}
    pIndex = 1
    MAX_PAGES = 20  # sample(무인증) 모드는 페이지가 진짜로 안 넘어갈 수 있어 안전장치로 상한을 둠
    while pIndex <= MAX_PAGES:
        data = _call({
            "STATBL_ID": STATBL_ID,
            "DTACYCLE_CD": DTACYCLE_CD,
            "ITM_ID": ITM_ID,
            "START_WRTTIME": ym,
            "END_WRTTIME": ym,
            "pIndex": pIndex,
            "pSize": pSize,
        })

        if isinstance(data, dict) and "RESULT" in data:
            # {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}} 케이스
            if pIndex == 1:
                raise ValueError(f"{year}.{month}: {data['RESULT'].get('MESSAGE')}")
            break

        head = data["SttsApiTblData"][0]["head"]
        total_count = next(h["list_total_count"] for h in head if "list_total_count" in h)
        rows = data["SttsApiTblData"][1]["row"]

        before = len(result)
        for r in rows:
            result[int(r["CLS_ID"])] = float(r["DTA_VAL"])

        if len(result) >= total_count or not rows or len(result) == before:
            # 마지막 조건: 페이지를 넘겨도 새 지역이 안 들어옴 -> sample 모드 한계로 판단하고 중단
            break
        pIndex += 1

    return result


def load_prices_by_var(year: int, month: int) -> dict:
    """{var_name: 만원/㎡ 원자료} — apt_price_logic.compute_row()에 바로 넣을 수 있는 형태.
    REB 원자료 단위는 천원/㎡ 이므로 10으로 나눠 만원/㎡로 맞춘다(KB 시트와 단위 통일)."""
    by_cls = load_month_prices_by_cls_id(year, month)
    result = {}
    missing = []
    for var, cls_id in CLS_ID_BY_VAR.items():
        if cls_id not in by_cls:
            missing.append(var)
            continue
        result[var] = by_cls[cls_id] / 10.0  # 천원/㎡ -> 만원/㎡
    return result, missing


def prev_year_month(year: int, month: int) -> tuple:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def load_prices_with_prev(year: int, month: int) -> tuple:
    """이번 달 + 전월 원자료를 함께 반환: (prices_by_var, prev_prices_by_var, missing)
    전월 조회가 실패하면(REB 미공표 등) prev_prices_by_var는 빈 dict — 전월대비 배지 없이 진행하면 됨."""
    prices, missing = load_prices_by_var(year, month)
    py, pm = prev_year_month(year, month)
    try:
        prev_prices, _ = load_prices_by_var(py, pm)
    except ValueError:
        prev_prices = {}
    return prices, prev_prices, missing


if __name__ == "__main__":
    import sys

    year, month = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (2026, 5)
    prices, missing = load_prices_by_var(year, month)
    print(f"{year}.{month}: {len(prices)}개 매핑, 누락 {len(missing)}개")
    if missing:
        print("  누락:", missing)
    for k in ["Gangnam_gu", "Suwon_si", "Dongducheon_si", "seo01_gu"]:
        if k in prices:
            print(f"  {k}: {prices[k]:.1f} 만원/㎡")
        time.sleep(0)  # (rate-limit 여유용, 현재 미사용)
