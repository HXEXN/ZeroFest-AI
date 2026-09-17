#!/usr/bin/env python3
"""Build the single consolidated ZeroFest report.

The four topic reports each answer one question. This one tells the whole story
in the order a reviewer needs it: what the problem is, what we built, what was
wrong with the data, what we fixed, and what we still cannot claim.

Nothing here is retyped. Live figures come from the same helpers the topic
reports use, and the evidence tables are imported from them, so the consolidated
document cannot drift away from its sources.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models.demand_model import FEATURES  # noqa: E402
from scripts.build_data_requirement_report import (  # noqa: E402
    saturation_point,
    stability_point,
    transfer_summary,
)
from scripts.build_problem_evidence_report import GAP, POLICY, SCALE, _rows  # noqa: E402
from scripts.build_synthetic_data_design_report import (  # noqa: E402
    BAKERY_TRACE,
    FRESHRETAIL_TRACE,
    _metrics,
)
from scripts.report_layout import Page, fonts, write_document  # noqa: E402

OUTPUT_DIR = ROOT / "outputs"
OUTPUT = OUTPUT_DIR / "ZeroFest_종합보고서.docx"
STUDY_PATH = OUTPUT_DIR / "data_requirement_study.json"

# Measurements taken on the dataset as it stood before the fixes described in
# section 4. They cannot be recomputed -- that dataset no longer exists -- so
# they are recorded here as the historical record they are.
BEFORE = {
    "duplicate_share": "89.2%",
    "censored_share": "51.5%",
    "leftover_zero_share": "99.3%",
    "discount_share": "0.06% (1,728행 중 1행)",
    "event_share": "상수 0",
    "temp_clock_corr": "0.906",
    "zero_target_share": "51.5%",
    "menus": "9종 중 3종만 생성",
    "holdout": "복사본 검증 · 오라클 R² 1.000",
}

DEFECTS = [
    ("연도·캠퍼스가 복사본", "9칸이 1개 실행의 복사본이라 검증 연도가 학습 연도의 결정론적 변환",
     "칸마다 다른 시드로 독립 시뮬레이션"),
    ("수요 검열 미처리", "타깃의 절반이 품절로 잘린 0인데 수요 0으로 학습",
     "censored_window_flag로 표시하고 학습·평가에서 제외"),
    ("폐기가 없는 데이터", "잔여재고 0인 메뉴-일이 99.3%. 폐기예측 모델인데 폐기가 없음",
     "준비 재고를 기대수요 × 0.85~1.45로 역산"),
    ("공연 편성 비활성", "경과 분과 하루 중 분을 혼용해 모든 공연 구간이 꺼짐",
     "시간 축을 개장 경과 분으로 통일"),
    ("할인 관측 부재", "할인이 적용된 행이 1,728행 중 1행",
     "메뉴 내 블록 무작위 배정으로 on/off 반복"),
    ("기온이 시계의 별칭", "기온을 시각의 sin 함수로 생성해 날씨 정보가 시간 정보의 중복",
     "일자별 추출 + AR(1) 잡음"),
    ("메뉴 3종만 생성", "유형 선택과 품목 선택이 같은 인덱스를 써서 가격이 유형의 재서술",
     "품목 인덱스를 분리해 9종 전부 생성"),
]

LAYERS = [
    ("ML 예측", "30분·1시간·종료 시점 판매량", "LLM이 수치를 만들지 않음"),
    ("규칙 엔진", "잔여비율로 LOW/MEDIUM/HIGH", ".env 임계값 · 결정론적"),
    ("LangGraph", "상태 로드부터 재예측까지 9개 노드", "분기와 순서가 코드에 명시"),
    ("업무 규칙", "조리중단·할인·이동·프로모션 후보", "입력 근거가 있는 규칙만"),
    ("사람", "실행 여부 최종 결정", "승인 전에는 PENDING"),
    ("LLM", "DB 스냅샷 기반 설명", "키가 없어도 grounded 답변"),
]


def build_pages(m: dict, study: dict, font_set: dict) -> list[Path]:
    curve = study["curve"]
    saturation = saturation_point(curve)
    stability = stability_point(curve)
    recommended = max(saturation, stability, key=lambda point: point["festivals"])
    transfer = transfer_summary(study["transfer"])
    lifts = m["lifts"]
    pages: list[Path] = []

    # --- P1 executive summary ------------------------------------------------
    page = Page(font_set)
    page.title("ZeroFest AI 종합보고서", "대학축제 잔여재고를 남기 전에 줄이는 AI 운영 시스템")
    page.heading("한 장 요약")
    page.table(
        ["항목", "내용"],
        [
            ["문제", "전국 고등교육기관 421개교가 매년 같은 구조의 축제를 치르지만, 행사 폐기물은 국가 통계 항목이 아니다"],
            ["접근", "폐기 후 처리가 아니라 예측 → 운영자 승인 → 수요 유도 → 재예측의 사전 예방 폐루프"],
            ["데이터", f"독립 시뮬레이션 축제 {m['cells']}회 · {m['rows']:,}행 · 피처 {m['feature_count']}개"],
            ["모델", f"GradientBoosting · MAE {m['mae']:.2f} (운영 기준선 {m['baseline_mae']:.2f} 대비 "
                    f"{(1 - m['mae'] / m['baseline_mae']):.0%} 개선)"],
            ["요구량", f"독립 축제 {int(recommended['festivals'])}회분이면 성능과 안정성이 함께 포화. "
                      "같은 실데이터 양이면 합성 사전학습이 항상 유리"],
            ["한계", "모든 수치는 합성 데이터 결과이며 실증 성능이 아니다"],
        ],
        [240, 1260],
        row_height=62,
    )
    page.heading("이번 개선의 핵심")
    page.body(
        "이 보고서에서 가장 중요한 내용은 새로 추가한 기능이 아니라, 우리가 만든 학습 데이터가 "
        "틀려 있었다는 사실과 그 수정이다. 이전에 보고하던 성능 수치는 유효하지 않았다."
    )
    page.table(
        ["지표", "수정 전", "수정 후"],
        [
            ["연도 간 중복 피처 행", BEFORE["duplicate_share"], f"{m['duplicate_share']:.2%}"],
            ["타깃이 잘린 관측", BEFORE["censored_share"], f"{m['censored_share']:.1%}"],
            ["잔여재고 0인 메뉴-일", BEFORE["leftover_zero_share"], f"{m['leftover_zero_share']:.0%}"],
            ["할인이 적용된 관측", BEFORE["discount_share"], f"{m['discount_share']:.1%}"],
            ["공연 종료 임박 구간", BEFORE["event_share"], f"{m['event_share']:.1%}"],
            ["기온과 시각의 상관", BEFORE["temp_clock_corr"], f"{m['temp_clock_corr']:.3f}"],
        ],
        [560, 470, 470],
        row_height=52,
    )
    page.note("수정 전 수치는 당시 데이터에서 측정한 기록이다. 그 데이터셋은 더 이상 존재하지 않아 재계산할 수 없다.")
    pages.append(page.save(OUTPUT_DIR / "master_page_1.png"))

    # --- P2 problem ----------------------------------------------------------
    page = Page(font_set)
    page.title("1. 문제", "특정 축제 한두 건의 일이 아니다")
    page.heading("1.1 모집단")
    page.table(["항목", "수치", "출처"], _rows(SCALE), [300, 860, 340])
    page.heading("1.2 근거가 사례에 머무는 이유")
    page.body(
        "2026년 9월 국회입법조사처는 행사에서 나오는 폐기물이 국가 폐기물 통계의 별도 항목이 "
        "아니라고 지적했다. 축제가 개별 관리 단위로만 취급되어 전국 단위로 비교할 근거 자체가 "
        "생산되지 않는다. 근거가 개별 사례에 머문 것은 조사 부족이 아니라 이 범주가 집계되지 "
        "않기 때문이다."
    )
    page.table(["항목", "내용", "출처"], _rows(GAP), [300, 860, 340])
    page.heading("1.3 현재 정책이 비운 자리")
    page.table(["항목", "수치", "출처"], _rows(POLICY[:3]), [300, 860, 340])
    page.body(
        "다회용기는 효과가 검증된 대책이지만 줄이는 대상은 용기 폐기물이다. 부스가 재료를 과잉 "
        "준비해 음식 자체가 남는 문제를 다루는 대책은 확인되지 않았다. 국회입법조사처가 제시한 "
        "사전 감량 방향에서 이 영역이 비어 있다."
    )
    pages.append(page.save(OUTPUT_DIR / "master_page_2.png"))

    # --- P3 service ----------------------------------------------------------
    page = Page(font_set)
    page.title("2. 서비스 구조", "예측에서 끝나지 않는 폐루프")
    page.body(
        "판매·재고 입력과 날씨·공연 정보를 읽어 30분 뒤 수요를 예측하고, 잔여재고 위험을 "
        "판정한 뒤 운영 Action 후보를 만든다. 운영자가 승인하기 전에는 아무것도 실행되지 않는다. "
        "승인된 할인은 학생 화면에 노출되고, 그 결과로 바뀐 판매·재고가 다시 예측 입력이 된다."
    )
    page.heading("2.1 책임 분리")
    page.table(["계층", "책임", "임의 판단 방지"], [list(row) for row in LAYERS], [230, 620, 650], row_height=52)
    page.heading("2.2 개입이 예측을 실제로 움직이는가")
    page.body(
        "할인을 승인하면 모델이 이를 새 개입으로 인식해 다음 30분 수요 예측을 올린다. 이미 30분 "
        "이상 적용된 할인은 최근 판매량에 반영되어 있으므로, 갓 적용된 할인만 별도 피처"
        "(new_discount_rate)로 분리한다. 이 구분이 없으면 모델은 할인을 최근 판매량과 중복된 "
        "변수로 배우고 '지금 할인하면 어떻게 되는가'에 답하지 못한다."
    )
    page.table(
        ["할인율", "합성 데이터 설계값", "모델이 복원한 값"],
        [[f"{rate}%", f"+{rate / 95 * 100:.1f}%", f"+{lifts[rate] * 100:.1f}%"] for rate in (10, 20, 30)],
        [300, 480, 720],
    )
    page.note(f"배정 균형 검정: 할인이 시작될 수 없는 초반 구간에서 두 군의 잠재 수요 비 {m['balance']:.3f}")
    pages.append(page.save(OUTPUT_DIR / "master_page_3.png"))

    # --- P4 data -------------------------------------------------------------
    page = Page(font_set)
    page.title("3. 합성 데이터", "축제가 돌아가는 세계를 만들고 관측한다")
    page.heading("3.1 왜 합성인가")
    page.body(
        "대학축제 부스의 분 단위 판매·재고 이력은 공개 데이터로 존재하지 않는다. 예측해야 하는 "
        "것은 매출이 아니라 잔여재고인데, 잔여재고는 준비량·소진 시각·할인 시점·공연 편성이 같은 "
        "축에 정렬되어야 복원된다. 실데이터가 이 조건을 만족하지 못하므로 그 구조를 명시적으로 "
        "설계했다."
    )
    page.heading("3.2 만든 것")
    page.table(
        ["구성", "내용"],
        [
            ["축제", f"{m['cells']}회 (3개 연도 × 3개 캠퍼스, 각각 다른 시드의 독립 실행)"],
            ["규모", "축제마다 3일 × 16–22시 × 12부스 × 부스당 4메뉴 × 4개 구역"],
            ["메뉴", "유형별 3종씩 9종 (닭꼬치·떡볶이·핫도그 / 아이스티·에이드·커피 / 와플·츄러스·쿠키)"],
            ["관측 단위", "초 이벤트 · 부스 1초 · 부스메뉴 1분 · 부스메뉴 30분(학습)"],
            ["운영 실태", f"메뉴-일 평균 준비 {m['stock_mean']:.0f}개 · 판매 {m['sold_mean']:.0f}개 · 잔여 중앙값 {m['leftover_median']:.0f}개"],
        ],
        [240, 1260],
        row_height=56,
    )
    page.heading("3.3 인과에서 출발한다")
    page.body(
        "분당 잠재 수요를 부스·메뉴 인기도, 공연 단계, 시간대, 날씨, 할인, 축제 일차의 곱으로 "
        "정의한 뒤 방문 팀 수를 뽑고 팀마다 구매 수량을 뽑아 합산한다. 실제 판매량은 잠재 수요와 "
        "현재 재고 중 작은 값이다. 이 제약 때문에 품절·할인·재고 소진 시점이 하나의 이야기로 연결된다."
    )
    page.table(
        ["설계한 효과", "의도", "데이터에서 확인"],
        [
            ["강수 민감도", "음료가 음식보다 덜 민감", f"음료 {m['rain_drink']:.3f} vs 음식 {m['rain_food']:.3f}"],
            ["공연 종료 임박", "수요 증가 구간", f"{m['stage_off']:.1f} → {m['stage_on']:.1f}개 / 30분"],
        ],
        [280, 420, 800],
    )
    pages.append(page.save(OUTPUT_DIR / "master_page_4.png"))

    # --- P5 the defects and the fixes ---------------------------------------
    page = Page(font_set)
    page.title("4. 데이터 개선", "무엇이 틀렸고 무엇을 고쳤는가")
    page.body(
        "이 절이 이번 작업의 핵심이다. 아래 일곱 가지는 모두 우리가 만든 데이터의 결함이며, "
        "이전에 보고하던 성능 수치를 무효로 만드는 것들이었다."
    )
    page.table(
        ["결함", "증상", "수정"],
        [list(row) for row in DEFECTS],
        [250, 700, 550],
        row_height=74,
    )
    page.note(
        "가장 큰 것은 첫 번째다. 9칸이 복사본이었으므로 '작년 행을 복사해 1.035를 곱하는' 규칙만으로 "
        "R² 1.000이 나왔다. 그런 분할에서 나온 성능 수치는 일반화와 무관하다."
    )
    pages.append(page.save(OUTPUT_DIR / "master_page_5.png"))

    # --- P6 variable provenance ---------------------------------------------
    page = Page(font_set)
    page.title("5. 변수 선정 근거", "합성 변수가 어느 실데이터 분석에서 왔는가")
    page.body(
        "변수는 임의로 고르지 않았다. 공개 실데이터 상관분석 두 건에서 확인된 관계를 근거로 "
        "넣거나, 근거를 들어 뺐다. 상관계수는 각 보고서가 공표한 값이며 재계산하지 않는다."
    )
    page.heading("5.1 French Bakery Daily Sales · 일 판매수량")
    page.table(
        ["실데이터 변수", "Pearson", "합성 데이터 반영", "모델 피처 여부"],
        [list(row) for row in BAKERY_TRACE[:6]],
        [290, 170, 470, 570],
        row_height=46,
    )
    page.heading("5.2 FreshRetailNet · 일 판매량")
    page.table(
        ["실데이터 변수", "Pearson", "합성 데이터 반영", "모델 피처 여부"],
        [list(row) for row in FRESHRETAIL_TRACE[:6]],
        [290, 170, 470, 570],
        row_height=46,
    )
    page.body(
        "추적 과정에서 실제로 설계를 바꾼 것이 하나 있다. 베이커리 1위 변수인 고객 티켓 수를 "
        "우리는 판매량 ÷ 2.0으로 만들고 있었다. 판매량의 재서술이라 독자적인 정보가 없었다. "
        "수요 생성을 팀 단위로 바꾸고 운영 화면의 주문 버튼 한 번이 한 팀이 되게 하자, "
        "최근 30분 주문 건수가 피처 중요도 3위가 되었다."
    )
    pages.append(page.save(OUTPUT_DIR / "master_page_6.png"))

    # --- P7 model and validation --------------------------------------------
    page = Page(font_set)
    page.title("6. 모델과 검증", "정직한 수치를 만드는 장치")
    page.heading("6.1 성능")
    page.table(
        ["구성", "MAE", "R²"],
        [
            ["운영 기준선 (직전 30분 유지)", f"{m['baseline_mae']:.2f}", f"{m['baseline_r2']:.3f}"],
            ["GradientBoosting", f"{m['mae']:.2f}", f"{m['r2']:.3f}"],
        ],
        [760, 360, 360],
        highlight=1,
    )
    page.note(
        f"피처 {m['feature_count']}개 · 학습 {m['train_rows']:,}행(2023–2024) · 시간 홀드아웃 {m['test_rows']:,}행(2025)"
    )
    page.heading("6.2 누수를 막는 네 가지")
    page.bullets([
        "타깃 창은 관측 시각 +1분부터 +30분. 최근 30분 판매량과 겹치지 않는다.",
        "최종 매출·최종 티켓 수·종료 시점 잔여재고는 입력에서 제외한다.",
        "2025년 전체를 시간 홀드아웃으로 두고, 칸마다 시드를 달리해 독립성을 만든다.",
        "품절로 잘린 타깃은 학습과 평가 양쪽에서 제외한다.",
    ])
    page.heading("6.3 분할이 실제로 독립인가")
    page.body(
        "복사본 검증에서는 작년 행을 복사해 성장률만 곱하는 오라클이 R² 1.000을 받았다. "
        "독립 생성으로 바꾼 뒤 같은 오라클을 돌리면 R²는 -0.216으로, 평균을 예측하는 것보다 "
        "나쁘다. 홀드아웃이 실제로 독립이라는 뜻이다."
    )
    page.note("모든 성능 수치는 합성 데이터 검증값이다. 실제 예측 정확도의 근거로 쓸 수 없다.")
    pages.append(page.save(OUTPUT_DIR / "master_page_7.png"))

    # --- P8 data requirement -------------------------------------------------
    page = Page(font_set)
    page.title("7. 데이터 요구량", "이 모델을 쓰려면 축제가 몇 회분 필요한가")
    page.body(
        "한 축제 안의 레코드는 같은 날씨·유동인구·메뉴 구성을 공유한다. 따라서 학습 단위는 행이 "
        f"아니라 독립 축제다. 축제 {study['train_festivals']}회를 후보로 두고, 학습에 쓰지 않은 "
        f"축제 {study['test_festivals']}회에서만 성능을 측정했다."
    )
    page.table(
        ["기준", "필요한 독립 축제 수", "MAE", "표준편차"],
        [
            ["정확도 포화", f"{int(saturation['festivals'])}회", f"{saturation['mae']:.2f}", f"±{saturation['mae_std']:.2f}"],
            ["결과 안정성", f"{int(stability['festivals'])}회", f"{stability['mae']:.2f}", f"±{stability['mae_std']:.2f}"],
        ],
        [420, 420, 320, 340],
        # Highlight whichever criterion is the binding one, not a fixed row.
        highlight=0 if recommended["festivals"] == saturation["festivals"] else 1,
    )
    page.body(
        f"축제 1회로 학습하면 어떤 축제를 뽑았느냐에 따라 MAE가 ±{curve[0]['mae_std']:.2f}까지 흔들린다. "
        f"둘 중 큰 값인 {int(recommended['festivals'])}회를 준비 기준으로 삼는다. 정확도가 멈춘 뒤에도 "
        "결과가 흔들린다면 그 수치는 아직 근거로 쓸 수 없다."
    )
    page.heading("7.2 실데이터가 한 번 들어왔을 때")
    page.table(
        ["전략", "사용한 실데이터", "MAE", "R²"],
        [
            [row["strategy"], f"{int(row['real_rows']):,}행", f"{row['mae']:.2f}", f"{row['r2']:.3f}"]
            for row in study["transfer"]
        ],
        [660, 300, 260, 280],
        row_height=46,
    )
    saving = transfer["best_saving"]
    lines = [
        "같은 양의 실데이터를 쓸 때 사전학습을 얹은 쪽이 모든 구간에서 낫다."
        if transfer["always_better"]
        else "같은 양의 실데이터 기준으로 "
             + " · ".join(f"{f:.0%}" for f in transfer["same_volume_wins"])
             + " 구간에서 사전학습이 낫다."
    ]
    if saving:
        small, large = saving
        lines.append(
            f"실데이터 {small:.0%}에 사전학습을 얹은 구성(MAE {transfer['pretrained'][small]['mae']:.2f})이 "
            f"실데이터 {large:.0%} 단독(MAE {transfer['real_only'][large]['mae']:.2f})보다 나아, 이 구간에서는 "
            f"실데이터 요구량이 약 {large / small:.0f}분의 1로 줄어든다."
        )
    else:
        lines.append("더 적은 실데이터로 더 많은 실데이터를 이기는 구간은 이번 실행에서 나타나지 않았다.")
    page.body(" ".join(lines))
    pages.append(page.save(OUTPUT_DIR / "master_page_8.png"))

    # --- P9 limits -----------------------------------------------------------
    page = Page(font_set)
    page.title("8. 한계와 다음 단계", "지금 주장할 수 없는 것")
    page.heading("8.1 한계")
    page.bullets([
        "학습 데이터가 전부 합성이다. 어떤 수치도 실증 성능의 근거가 아니다.",
        "설계 효과 복원은 설계 일관성 검증이지 현실 타당성 검증이 아니다.",
        "요구량 실험의 '실데이터'도 분포만 이동시킨 합성 축제다.",
        "대학축제 음식 폐기량을 직접 집계한 국내 공식 통계는 확인되지 않았다.",
        "판매 품목 수는 MVP가 부스당 메뉴 1개라 상수가 되어 모델에 넣지 못했다.",
    ])
    page.heading("8.2 다음 단계")
    page.table(
        ["순서", "할 일", "판단 기준"],
        [
            ["1", "합성 축제 8회 이상으로 출시 전 모델을 준비", "학습곡선 안정성 지점"],
            ["2", "첫 실축제는 합성 모델을 그대로 쓰고 종료 후 잔차만 보정", "전이 실험 결과"],
            ["3", "같은 실험 스크립트를 실데이터로 다시 실행", "이 추정이 맞았는지 검증"],
            ["4", "부스별 준비량·판매량·잔여량을 공개 기록으로 축적", "행사 폐기물 통계 공백을 메움"],
        ],
        [140, 800, 560],
        row_height=56,
    )
    page.heading("8.3 이 제품의 1차 기여")
    page.body(
        "행사 폐기물이 통계 항목이 아닌 상황에서, 부스 단위 준비량과 잔여량이 같은 타임스탬프로 "
        "남는 것 자체가 처음 만들어지는 자료다. 예측 정확도는 그 다음 단계의 이야기다. "
        "측정 체계가 없는 영역에서는 측정 자체가 첫 번째 기여가 된다."
    )
    pages.append(page.save(OUTPUT_DIR / "master_page_9.png"))
    return pages


def main() -> None:
    if not STUDY_PATH.exists():
        raise FileNotFoundError(f"{STUDY_PATH} 가 없습니다. scripts/run_data_requirement_study.py 를 먼저 실행하세요.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pages = build_pages(_metrics(), json.loads(STUDY_PATH.read_text()), fonts())
    write_document(pages, OUTPUT)
    print(f"Wrote {OUTPUT} ({len(pages)} pages)")


if __name__ == "__main__":
    main()
