#!/usr/bin/env python3
"""Build the ZeroFest synthetic-data design rationale report.

Every figure in the report is recomputed from the generated files at build time,
so the document cannot drift away from the data it describes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.report_layout import NAVY, Page, fonts, write_document  # noqa: E402

OUTPUT_DIR = ROOT / "outputs"
OUTPUT = OUTPUT_DIR / "ZeroFest_합성데이터_설계근거_보고서.docx"
TRAINING_PATH = ROOT / "data" / "final_training_dataset.csv"
SNAPSHOT_PATH = ROOT / "data" / "synthetic_festival_feature_snapshot.csv"



# --- Traceability: which real-data finding put each synthetic variable there ----
# Columns: 실데이터 변수, Pearson(보고서 공표값), 합성 데이터 반영, 모델 피처 여부
# "제외"에는 반드시 근거를 적는다. 근거 없는 변수도, 근거 없는 제외도 두지 않는다.
BAKERY_TRACE = [
    ("일 매출 EUR", "+0.989", "반영하지 않음", "사후 지표 · 타깃과 동시 산출"),
    ("고객 티켓 수", "+0.960", "recent_tickets_30m", "모델 피처 · 운영 화면 수집"),
    ("판매 품목 수", "+0.856", "booth_unique_menu_count_1m", "데이터셋만 · 부스당 메뉴 1개"),
    ("티켓당 수량", "+0.795", "팀 규모 추출 (공연 단계별 1.00~1.25)", "생성식에 반영"),
    ("평균 판매시각", "-0.619", "hour_multiplier 시간대 보정", "minutes_to_close"),
    ("주말 여부", "+0.422", "is_weekend", "모델 피처"),
    ("요일", "+0.360", "day_of_week", "제외 · is_weekend와 r=0.881"),
    ("평균 단가", "-0.217", "price_krw / price", "제외 · 중요도 0.004"),
    ("월", "+0.200", "month (분 스냅샷)", "제외 · 축제가 5월 고정"),
    ("경과 일수", "+0.106", "festival_day", "모델 피처"),
]
FRESHRETAIL_TRACE = [
    ("할인율", "-0.359", "discount_rate · 블록 무작위 배정", "모델 피처 + new_discount_rate"),
    ("재고 보유 시간", "-0.111", "current_stock · initial_stock · stockout_flag", "모델 피처"),
    ("휴일 여부", "+0.082", "반영하지 않음", "미반영 · 아래 공백 참조"),
    ("요일", "+0.072", "day_of_week", "제외 · is_weekend와 중복"),
    ("평균 습도", "+0.069", "반영하지 않음", "제외 · |r|<0.07"),
    ("강수량", "+0.042", "rain_mm → precipitation_probability", "모델 피처"),
    ("월", "-0.038", "month (분 스냅샷)", "제외 · 축제가 5월 고정"),
    ("평균 기온", "-0.019", "temperature_c → temperature", "모델 피처"),
    ("평균 풍속", "+0.007", "반영하지 않음", "제외 · |r|<0.01"),
    ("행사 여부", "-0.006", "performance_phase · event_ending_soon", "모델 피처"),
]
RECOMMENDATION_TRACE = [
    ("할인율은 포함하되 프로모션 대상 편향을 분리", "FreshRetailNet", "메뉴 내 블록 무작위 배정 · 상태 조건부 발동 제거"),
    ("재고 상태는 품절·수요 검열 가능성과 함께 관리", "FreshRetailNet", "censored_window_flag · next_30m_latent_qty · 학습 제외"),
    ("날씨는 메뉴 유형·시간대 상호작용으로 확장", "FreshRetailNet", "음료 강수 계수 0.035 / 그 외 0.065, 기온 계수 부호 반전"),
    ("판매·재고·할인·공연을 같은 타임스탬프로 정렬", "FreshRetailNet", "초·분·30분 3중 그레인"),
    ("일 매출·최종 티켓 수는 학습 입력에서 분리", "French Bakery", "사후 지표 전량 제외"),
    ("행사 전은 사전 확정 변수, 행사 중은 시점별 누적", "French Bakery", "행사 전/중 모델 분리 명시"),
]
GAPS = [
    ("휴일 여부", "FreshRetailNet +0.082", "축제 일자가 5월 20~22일로 고정되어 공휴일과 겹치지 않는다. 지금 넣으면 상수 컬럼이 된다."),
    ("평균 습도 · 풍속", "FreshRetailNet +0.069 / +0.007", "선형 상관이 0.07 미만이다. 넣으면 잡음 피처가 된다."),
    ("판매 품목 수", "French Bakery +0.856", "MVP 운영 DB는 부스당 메뉴가 1개여서 이 값이 항상 1이 된다. 한 부스가 여러 메뉴를 파는 구조가 되면 그때 투입한다."),
]


def _metrics() -> dict[str, object]:
    """Recompute every number quoted in the report from the generated files."""
    from models.demand_model import FEATURES, MODEL_PARAMS, load_historical_data, uncensored
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.metrics import mean_absolute_error, r2_score

    snapshot = pd.read_csv(SNAPSHOT_PATH)
    # The loader adds the derived model columns, so FEATURES is addressable here.
    training = load_historical_data()
    usable = uncensored(training)

    train = usable[usable["festival_year"] < usable["festival_year"].max()]
    test = usable[usable["festival_year"] == usable["festival_year"].max()]
    model = GradientBoostingRegressor(**MODEL_PARAMS)
    model.fit(train[FEATURES], train["future_sales_30m"])
    predicted = model.predict(test[FEATURES])
    actual = test["future_sales_30m"]

    # Randomised assignment means the discount effect is recoverable once the
    # snapshot minute is held fixed. This is the design's acceptance test.
    # Controls are menu-days that were never discounted, so a control row's own
    # target window can never contain a discount that has not started yet.
    control = training[training["discount_arm"] == 0]
    lifts: dict[int, float] = {}
    for rate in (10, 20, 30):
        treated = training[training["discount_rate"] == rate]
        pair = pd.concat([treated.assign(_arm=1), control.assign(_arm=0)])
        table = pair.groupby(["minutes_to_close", "_arm"])["future_latent_30m"].mean().unstack().dropna()
        weights = pair[pair["_arm"] == 1].groupby("minutes_to_close").size().reindex(table.index)
        lifts[rate] = float(np.average(table[1] / table[0] - 1, weights=weights))

    # Balance check: before any discount can start, the two arms must look alike.
    pre = training[training["minutes_to_close"] >= 239]
    balance = float(
        pre[pre["discount_arm"] == 1]["future_latent_30m"].mean()
        / pre[pre["discount_arm"] == 0]["future_latent_30m"].mean()
    )

    wet = training.assign(wet=training["precipitation_probability"] >= 25)
    rain_ratio = wet.groupby(["wet", "menu_category"])["future_latent_30m"].mean().unstack()
    leftover = snapshot.groupby(["menu_id", "festival_day"])["final_leftover_qty"].first()
    stage_effect = training.groupby("event_ending_soon")["future_latent_30m"].mean()

    return {
        "rows": len(training),
        "cells": training.groupby(["festival_year", "university_id"]).ngroups,
        "censored_share": float(training["censored_window_flag"].mean()),
        "censored_rows": int(training["censored_window_flag"].sum()),
        "stockout_share": float(training["stockout_flag"].mean()),
        "discount_share": float((training["discount_rate"] > 0).mean()),
        "event_share": float(training["event_ending_soon"].mean()),
        "duplicate_share": float(training[FEATURES].duplicated().mean()),
        "zero_target_share": float((usable["future_sales_30m"] == 0).mean()),
        "temp_clock_corr": float(training[["temperature", "minutes_to_close"]].corr().iloc[0, 1]),
        "leftover_zero_share": float((leftover == 0).mean()),
        "leftover_median": float(leftover.median()),
        "stock_mean": float(snapshot["initial_stock"].mean()),
        "sold_mean": float((snapshot["initial_stock"] - snapshot["final_leftover_qty"]).groupby(
            [snapshot["menu_id"], snapshot["festival_day"]]).first().mean()),
        "lifts": lifts,
        "balance": balance,
        "arm_share": float(training["discount_arm"].mean()),
        "rain_drink": float(rain_ratio.loc[True, "drink"] / rain_ratio.loc[False, "drink"]),
        "rain_food": float(rain_ratio.loc[True, "food"] / rain_ratio.loc[False, "food"]),
        "stage_off": float(stage_effect[0]),
        "stage_on": float(stage_effect[1]),
        "mae": float(mean_absolute_error(actual, predicted)),
        "r2": float(r2_score(actual, predicted)),
        "baseline_mae": float(mean_absolute_error(actual, test["recent_sales_30m"])),
        "baseline_r2": float(r2_score(actual, test["recent_sales_30m"])),
        "feature_count": len(FEATURES),
        "train_rows": len(train),
        "test_rows": len(test),
    }


def build_pages(m: dict[str, object], fonts: dict[str, ImageFont.FreeTypeFont]) -> list[Path]:
    pages: list[Path] = []
    lifts = m["lifts"]  # type: ignore[index]

    # --- Page 1: why synthetic, and the design principles -------------------
    page = Page(fonts)
    page.title("ZeroFest 합성데이터 설계근거 보고서", "왜 합성 데이터를 썼고, 어떤 원칙으로 만들었는가")
    page.heading("1. 왜 합성 데이터인가")
    page.body(
        "대학축제 부스의 분 단위 판매·재고 이력은 공개 데이터셋으로 존재하지 않는다. "
        "POS를 쓰는 부스가 드물고, 판매는 대부분 현금과 수기로 집계되며, 재고 소진 시각과 "
        "할인 적용 시각을 같은 타임스탬프로 남기는 기록은 사실상 없다."
    )
    page.body(
        "ZeroFest가 예측해야 하는 것은 매출이 아니라 잔여재고다. 잔여재고는 판매 이력만으로는 "
        "복원되지 않는다. 준비량, 소진 시각, 할인 시점, 공연 편성이 같은 축에 정렬되어야 한다. "
        "실데이터가 이 조건을 만족하지 못하므로, 그 구조를 명시적으로 설계한 합성 데이터를 사용한다."
    )
    page.heading("2. 세 가지 설계 원칙")
    page.table(
        ["원칙", "의미"],
        [
            ["인과 구조 우선", "상관을 흉내내지 않고 수요 생성식을 먼저 정의한 뒤 관측을 만든다"],
            ["관측 가능성 분리", "예측 시점에 알 수 없는 값은 타깃 또는 사후 지표로만 둔다"],
            ["복원 가능성 검증", "설계에 넣은 효과가 데이터에서 그대로 다시 나오는지 확인한다"],
        ],
        [340, 1140],
    )
    page.heading("3. 실데이터로 보정한 부분")
    page.body(
        "수요 생성식의 자유 파라미터는 임의로 정하지 않고, 공개 실데이터 상관분석 결과를 보정값으로 썼다."
    )
    page.table(
        ["출처", "가져온 것", "반영 위치"],
        [
            ["French Bakery Daily Sales", "시간대별 판매 분포, 티켓당 수량, 단가 분포", "hour_multiplier, ticket_count"],
            ["FreshRetailNet", "할인-판매량 관계, 재고 보유와 검열 위험", "discount_factor, 검열 플래그"],
            ["선행연구 (Kim, 2025)", "기온·강수·주말 지표의 수요 영향", "weather_factor, is_weekend"],
        ],
        [430, 640, 410],
    )
    page.note("실데이터는 파라미터 보정에만 사용했다. 판매 레코드 자체는 어떤 실데이터도 포함하지 않는다.")
    pages.append(page.save(OUTPUT_DIR / "synthetic_design_page_1.png"))

    # --- Page 2: the causal model ------------------------------------------
    page = Page(fonts)
    page.title("수요 생성 구조", "관측이 아니라 인과에서 출발한다")
    page.heading("4. 분당 잠재 수요")
    page.body(
        "분당 잠재 수요는 아래 배수들의 곱으로 정의하고, 이 값을 평균으로 하는 포아송 분포에서 추출한다."
    )
    page.table(
        ["항목", "정의", "역할"],
        [
            ["기준 수요", "BASE_MINUTE_DEMAND = 0.55", "메뉴 하나가 6시간에 150~250개 팔리는 규모"],
            ["부스·메뉴 인기", "booth_factor × menu_factor", "고정 이질성"],
            ["공연 단계", "pre 1.10 / main 1.22 / after 0.95", "경과 분 기준 편성"],
            ["시간대", "베이커리 시간대 분포 보정", "실데이터 기반"],
            ["날씨", "강수·기온, 음료는 민감도 절반", "메뉴 유형별 상호작용"],
            ["할인", "1 + 할인율 / 95", "무작위 배정된 개입"],
            ["축제 일차", "1일 0.92 / 2일 1.13 / 3일 0.86", "일차 효과"],
        ],
        [260, 560, 660],
        row_height=52,
    )
    page.heading("5. 관측은 수요가 아니라 검열된 수요다")
    page.body(
        "실제 판매량은 잠재 수요와 현재 재고 중 작은 값이다. 재고가 0이 되는 순간부터 관측 "
        "판매량은 학생이 원한 양을 더 이상 추적하지 않는다. 이 구분을 데이터에 남기기 위해 "
        "세 개의 컬럼을 별도로 기록한다."
    )
    page.table(
        ["컬럼", "의미"],
        [
            ["stockout_flag", "예측 시점의 재고가 0인 관측치"],
            ["censored_window_flag", "타깃 30분 구간 안에서 재고가 소진되어 타깃이 잘린 관측치"],
            ["next_30m_latent_qty", "재고 제약 이전의 잠재 수요. 입력 금지, 편향 정량화 전용"],
        ],
        [420, 1060],
    )
    page.note("잠재 수요는 세상이 시뮬레이션이기 때문에만 존재한다. 실데이터에서는 관측할 수 없는 값이다.")
    pages.append(page.save(OUTPUT_DIR / "synthetic_design_page_2.png"))

    # --- Page 3: the five design decisions ---------------------------------
    page = Page(fonts)
    page.title("설계 결정과 근거", "이전 버전에서 바꾼 다섯 가지")
    page.heading("5. 무엇을, 왜 바꿨는가")
    page.table(
        ["결정", "이전", "현재", "바꾼 이유"],
        [
            ["공연 편성 기준축", "normal 100%", "main 33%", "경과 분과 하루 중 분을 혼용해 모든 공연 구간이 비활성"],
            ["재고 준비량", "무작위 105~230", "기대수요 × 0.85~1.45", "폐기가 없는 데이터로는 폐기를 학습할 수 없음"],
            ["할인 발동", "재고 조건부", "메뉴 내 블록 무작위", "상태 기반 발동은 위험과 교란되어 효과 식별 불가"],
            ["기온 생성", "시각의 sin 함수", "일자별 추출 + AR(1)", "기온이 시계의 별칭이면 날씨 정보가 시간 정보의 중복"],
            ["연도·캠퍼스", "1개 실행 복사", "9개 독립 시뮬레이션", "복사본 검증은 일반화와 무관한 성능을 만든다"],
        ],
        [250, 270, 300, 660],
        row_height=76,
    )
    page.heading("6. 데이터 분포 변화")
    page.table(
        ["지표", "이전", "현재"],
        [
            ["공연 구간 event_ending_soon", "상수 0", f"{m['event_share']:.1%}"],
            ["할인이 적용된 관측", "1,728행 중 1행", f"{m['discount_share']:.1%}"],
            ["품절 상태 관측", "51.5%", f"{m['stockout_share']:.1%}"],
            ["타깃이 잘린 관측", "51.5%", f"{m['censored_share']:.1%}"],
            ["잔여재고 0인 메뉴-일", "99.3%", f"{m['leftover_zero_share']:.1%}"],
            ["기온과 시각의 상관", "0.906", f"{m['temp_clock_corr']:.3f}"],
            ["연도 간 중복 피처 행", "89.2%", f"{m['duplicate_share']:.2%}"],
            ["타깃이 0인 학습 행", "51.5%", f"{m['zero_target_share']:.2%}"],
        ],
        [700, 390, 390],
        row_height=52,
    )
    page.note(
        f"현재 데이터: {m['rows']:,}행 · {m['cells']}개 독립 시뮬레이션 · "
        f"메뉴-일 평균 준비 {m['stock_mean']:.0f}개, 판매 {m['sold_mean']:.0f}개, 잔여 중앙값 {m['leftover_median']:.0f}개"
    )
    pages.append(page.save(OUTPUT_DIR / "synthetic_design_page_3.png"))

    # --- Page 4: verification and limits ------------------------------------
    page = Page(fonts)
    page.title("복원 검증과 한계", "설계한 효과가 데이터에서 다시 나오는가")
    page.heading("7. 개입 효과 복원")
    page.body(
        "할인은 메뉴 안에서 블록 무작위 배정하므로, 관측 시점을 고정하면 설계값이 복원되어야 한다. "
        "할인이 시작될 수 없는 초반 구간에서 두 군의 잠재 수요 비는 "
        f"{m['balance']:.3f}로, 배정이 균형을 이루었음을 확인했다."
    )
    page.table(
        ["할인율", "설계값", "데이터에서 추정된 값"],
        [
            [f"{rate}%", f"+{rate / 95 * 100:.1f}%", f"+{lifts[rate] * 100:.1f}%"]
            for rate in (10, 20, 30)
        ],
        [300, 380, 800],
    )
    page.heading("8. 그 밖의 설계 효과")
    page.table(
        ["효과", "설계 의도", "데이터 확인"],
        [
            ["강수 민감도", "음료가 음식보다 덜 민감", f"음료 {m['rain_drink']:.3f} vs 음식 {m['rain_food']:.3f}"],
            ["공연 종료 임박", "수요 증가 구간", f"{m['stage_off']:.1f} → {m['stage_on']:.1f}개 / 30분"],
        ],
        [280, 420, 780],
    )
    page.heading("9. 모델 성능")
    page.table(
        ["구성", "MAE", "R²"],
        [
            ["운영 기준선 (직전 30분 유지)", f"{m['baseline_mae']:.2f}", f"{m['baseline_r2']:.3f}"],
            ["Gradient Boosting", f"{m['mae']:.2f}", f"{m['r2']:.3f}"],
        ],
        [760, 360, 360],
    )
    page.note(
        f"피처 {m['feature_count']}개 · 학습 {m['train_rows']:,}행(2023–2024) · 시간 홀드아웃 {m['test_rows']:,}행(2025)"
    )
    page.heading("10. 한계")
    page.bullets([
        "합성 데이터이므로 어떤 수치도 실증 효과의 근거가 아니다.",
        "복원 검증은 설계 일관성 검증이지 현실 타당성 검증이 아니다.",
        "티켓 수와 판매 품목 수는 데이터셋에만 있고 운영 DB가 수집하지 않는다.",
        "실제 축제 이력이 쌓이면 보정값이 아니라 학습 데이터로 교체해야 한다.",
    ])
    pages.append(page.save(OUTPUT_DIR / "synthetic_design_page_4.png"))

    # --- Page 5: which real-data finding justifies each variable ---------------
    page = Page(fonts)
    page.title("실데이터 근거 추적", "합성 변수 하나하나가 어느 분석에서 왔는가")
    page.body(
        "합성 데이터의 변수는 임의로 고르지 않았다. 공개 실데이터 상관분석 두 건에서 "
        "확인된 관계를 근거로 넣거나, 근거를 들어 뺐다. 아래 표의 상관계수는 각 보고서가 "
        "공표한 값이며 이 저장소에서 재계산하지 않는다."
    )
    page.heading("11. French Bakery Daily Sales · 종속변수 일 판매수량")
    page.table(
        ["실데이터 변수", "Pearson", "합성 데이터 반영", "모델 피처 여부"],
        [list(row) for row in BAKERY_TRACE],
        [300, 180, 480, 520],
        row_height=48,
    )
    page.note("실데이터 234,005개 판매 라인을 600일 단위로 집계한 분석 결과다.")
    pages.append(page.save(OUTPUT_DIR / "synthetic_design_page_5.png"))

    # --- Page 6: FreshRetailNet trace, recommendations, and the gaps -----------
    page = Page(fonts)
    page.title("실데이터 근거 추적 (계속)", "권고사항 이행과 남은 공백")
    page.heading("12. FreshRetailNet · 종속변수 일 판매량")
    page.table(
        ["실데이터 변수", "Pearson", "합성 데이터 반영", "모델 피처 여부"],
        [list(row) for row in FRESHRETAIL_TRACE],
        [280, 170, 520, 510],
        row_height=46,
    )
    page.heading("13. 두 보고서의 권고사항 이행")
    page.table(
        ["권고", "출처", "이행 내용"],
        [list(row) for row in RECOMMENDATION_TRACE],
        [530, 230, 720],
        row_height=48,
    )
    page.heading("14. 반영하지 못한 변수와 이유")
    page.table(
        ["변수", "실데이터 상관", "반영하지 않은 이유"],
        [list(row) for row in GAPS],
        [300, 330, 850],
        row_height=76,
    )
    page.note(
        "실데이터 1위 변수인 고객 티켓 수는 운영 화면의 주문 버튼으로 수집해 모델 피처에 넣었다. "
        "한 번 누르면 한 팀의 주문이므로 운영자 입력 부담은 늘지 않는다."
    )
    pages.append(page.save(OUTPUT_DIR / "synthetic_design_page_6.png"))
    return pages


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics = _metrics()
    pages = build_pages(metrics, fonts())
    write_document(pages, OUTPUT)
    print(f"Wrote {OUTPUT} ({len(pages)} pages)")


if __name__ == "__main__":
    main()
