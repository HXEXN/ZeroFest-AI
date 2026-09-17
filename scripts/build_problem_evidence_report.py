#!/usr/bin/env python3
"""Build the problem-universality evidence report.

The review noted that ZeroFest's problem statement leans on one or two festival
anecdotes. This document collects public statistics and policy findings behind a
single source of truth: EVIDENCE below feeds both docs/problem_evidence.md and
the docx in outputs/, so the two can never disagree.

Every row carries its source. Figures published by third parties are quoted as
published and are not recomputed here.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.report_layout import Page, fonts, write_document  # noqa: E402

OUTPUT_DIR = ROOT / "outputs"
OUTPUT = OUTPUT_DIR / "ZeroFest_문제_보편성_근거_보고서.docx"
MARKDOWN = ROOT / "docs" / "problem_evidence.md"

SOURCES = {
    "kess": ("교육부·한국교육개발원, 2025년 교육기본통계", "https://kedi.re.kr/khome/mobile2/announce/selectAnnounceForm.do?article_sq_no=36108"),
    "archives": ("국가기록원, 기록으로 만나는 대한민국 · 대학축제", "https://theme.archives.go.kr/next/koreaOfRecord/uvFestival.do"),
    "lineup": ("위키트리, 2026 전국 대학교 축제 라인업·일정", "https://www.wikitree.co.kr/articles/1135403"),
    "green": ("녹색연합, 대학 축제 쓰레기 실태 설문 (2024.10.10~11.15)", "https://www.greenkorea.org/activity/living-environment/zerowaste/110238/"),
    "hkbs": ("한국환경신문, 대학 축제 넘쳐나는 쓰레기로 몸살", "https://www.hkbs.co.kr/news/articleView.html?idxno=783218"),
    "ohmynews": ("오마이뉴스, 축제 끝난 대학 쓰레기는 얼마나 나왔을까 (2017)", "https://www.ohmynews.com/NWS_Web/View/at_pg.aspx?CNTN_CD=A0002329282"),
    "nars": ("국회입법조사처, 문화예술 축제·행사의 자원순환 관리체계 구축 과제 (2026.9.7)", "https://www.energydaily.co.kr/news/articleView.html?idxno=202940"),
    "me_food": ("환경부, 음식물류 폐기물 발생 현황", "https://stat.me.go.kr/portal/stat/easyStatPage/DT_106N_29_2020005.do"),
    "ghg": ("그린포스트코리아, 온실가스 주범 음식물쓰레기 연간 885만톤", "https://www.greenpostkorea.co.kr/news/articleView.html?idxno=127566"),
    "unep": ("UNEP Food Waste Index 인용 보도 (그리니엄)", "https://greenium.kr/news/32032/"),
}

SCALE = [
    ("전국 고등교육기관", "421개교 (일반대학 189 · 전문대학 130)", "kess"),
    ("재학생 규모", "재적학생 301만 6,724명", "kess"),
    ("축제 보편성", "1987년경 전국 대부분 대학이 대동제 형태로 개최", "archives"),
    ("개최 집중도", "2026년 봄 주요 20개교가 5월 6~29일 3주에 집중", "lineup"),
]

REALITY = [
    ("일회용기 사용률", "92% (다회용기 사용 경험 17%)", "green"),
    ("문제 심각성 인식", "응답자 10명 중 8명이 '심각하다'", "green"),
    ("분리배출 실패", "55%가 분리수거함 부족으로 재활용품과 쓰레기를 혼합 배출", "green"),
    ("단일 축제 배출량", "고려대 2017 축제 기준 주류병 약 1만 병 · 100L 봉투 1,500장", "ohmynews"),
    ("감축 실적 사례", "서울대 2023 봄축제에서 일회용기 8,600개 이상 감축", "hkbs"),
]

GAP = [
    ("통계 항목 부재", "현행 폐기물 통계에 '행사 폐기물'이 별도 항목으로 없음", "nars"),
    ("비교 체계 부재", "축제를 개별 관리 단위로 취급해 발생·감량 실적의 일관된 추적이 어려움", "nars"),
    ("정책 방향", "보고서 결론은 '사후 처리에서 사전 감량으로'", "nars"),
]

POLICY = [
    ("다회용기 도입률", "지자체 계획 축제 1,170개 중 340개(29.1%)만 도입", "nars"),
    ("강진군 5개 축제", "폐기물 24%↓ · 일회용품 37%↓ · 온실가스 39%↓", "nars"),
    ("인천 펜타포트", "4일간 다회용기 275,370개 사용, 회수율 98%", "nars"),
    ("환경부 시범 축제", "방문객 1인당 폐기물 평균 36.7% 감소", "green"),
]

BACKGROUND = [
    ("음식물류 폐기물", "하루 약 1만 4천 톤 · 전체 쓰레기의 28.7%", "me_food"),
    ("온실가스", "음식물쓰레기에서 연간 885만 톤 배출", "ghg"),
    ("1인당 배출", "연 95kg", "unep"),
]


def _rows(items: list[tuple[str, str, str]]) -> list[list[str]]:
    return [[label, value, SOURCES[key][0].split(",")[0]] for label, value, key in items]


def build_pages(font_set: dict) -> list[Path]:
    pages: list[Path] = []
    widths = [300, 860, 340]

    page = Page(font_set)
    page.title("ZeroFest 문제 보편성 근거", "이 문제가 특정 축제 한두 건의 일인가")
    page.heading("1. 문제가 발생하는 모집단")
    page.body(
        "대학 축제는 일부 대학의 행사가 아니다. 전국 고등교육기관 전체가 매년 "
        "같은 구조의 행사를 치르고, 그 대부분이 봄과 가을 각 3주 안에 몰린다. "
        "같은 문제가 같은 시기에 수백 곳에서 동시에 반복된다는 뜻이다."
    )
    page.table(["항목", "수치", "출처"], _rows(SCALE), widths)
    page.heading("2. 폐기 실태")
    page.body(
        "대학 축제 폐기물은 이미 여러 조사에서 확인된 사실이다. 다만 아래 수치는 "
        "대부분 용기·일회용품에 관한 것이며, 음식 자체가 얼마나 남는지를 센 조사는 없다."
    )
    page.table(["항목", "수치", "출처"], _rows(REALITY), widths)
    pages.append(page.save(OUTPUT_DIR / "problem_evidence_page_1.png"))

    page = Page(font_set)
    page.title("근거가 사례에 머무는 이유", "자료가 부족한 것이 아니라 항목이 없다")
    page.heading("3. 국회입법조사처가 확인한 통계 공백")
    page.body(
        "2026년 9월 국회입법조사처는 축제·행사 폐기물 관리체계를 다룬 보고서에서, "
        "행사에서 나오는 폐기물이 국가 폐기물 통계의 별도 항목이 아니라는 점을 지적했다. "
        "축제가 개별 관리 단위로만 취급되기 때문에 전국 단위로 비교할 근거 자체가 만들어지지 않는다."
    )
    page.table(["항목", "내용", "출처"], _rows(GAP), widths)
    page.body(
        "즉 ZeroFest의 근거가 개별 사례에 의존한 것은 자료 조사를 덜 해서가 아니라, "
        "국가 통계가 이 범주를 집계하지 않기 때문이다. 이것은 기획의 약점이 아니라 "
        "해결해야 할 문제의 일부다."
    )
    page.heading("4. 그래서 제품의 1차 기여는 예측 이전에 측정이다")
    page.bullets([
        "부스 단위 준비량·판매량·잔여량을 같은 타임스탬프로 남긴다.",
        "축제가 끝나면 '얼마나 준비해 얼마나 남았는가'가 처음으로 숫자로 남는다.",
        "이 기록이 쌓여야 전국 비교와 정책 근거가 만들어진다.",
        "예측 정확도는 그 다음 단계의 이야기다.",
    ])
    page.note(
        "이 관점은 제품 목표를 낮추는 것이 아니라 순서를 분명히 하는 것이다. "
        "측정 체계가 없는 영역에서는 측정 자체가 첫 번째 기여가 된다."
    )
    pages.append(page.save(OUTPUT_DIR / "problem_evidence_page_2.png"))

    page = Page(font_set)
    page.title("정책 흐름과 빈자리", "모든 대책이 용기를 향해 있다")
    page.heading("5. 현재 정책은 다회용기에 집중되어 있다")
    page.table(["항목", "수치", "출처"], _rows(POLICY), widths)
    page.body(
        "다회용기는 효과가 검증된 대책이다. 다만 다회용기가 줄이는 것은 '용기' 폐기물이다. "
        "부스가 재료를 과잉 준비해 음식 자체가 남는 문제는 어떤 대책도 다루지 않는다. "
        "국회입법조사처가 제시한 '사전 감량'에서, 음식 수요 자체를 미리 맞추는 영역이 비어 있다."
    )
    page.heading("6. 시장의 빈자리")
    page.body(
        "수요예측과 재고 최적화 솔루션은 프랜차이즈·리테일·식품유통 등 상시 운영 사업자를 "
        "전제로 만들어져 있다. 연 1~2회, 3일, 현금과 수기로 운영되는 대학 학생회는 "
        "그 제품들의 대상이 아니다. 도입 비용과 학습 곡선을 감당할 조직도 아니다."
    )
    page.table(
        ["구분", "기존 솔루션", "대학 축제"],
        [
            ["운영 주기", "상시", "연 1~2회 · 3일"],
            ["운영 주체", "전문 관리자", "매년 바뀌는 학생회"],
            ["데이터", "POS 누적 이력", "현금·수기, 이력 없음"],
            ["도입 여력", "구독료·교육 가능", "예산·인력 모두 부족"],
        ],
        [280, 610, 610],
    )
    page.heading("7. 배경 통계")
    page.table(["항목", "수치", "출처"], _rows(BACKGROUND), widths)
    page.heading("8. 남은 한계")
    page.bullets([
        "대학 축제의 '음식' 폐기량을 직접 집계한 국내 공식 통계는 확인되지 않았다.",
        "위 수치들은 용기·일회용품 중심이므로 음식 폐기 규모의 직접 증거는 아니다.",
        "파일럿에서 부스별 잔여량을 실측하는 것이 이 공백을 메우는 첫 단계다.",
    ])
    pages.append(page.save(OUTPUT_DIR / "problem_evidence_page_3.png"))
    return pages


def write_markdown() -> None:
    def section(title: str, items: list[tuple[str, str, str]]) -> str:
        lines = [f"## {title}", "", "| 항목 | 수치 | 출처 |", "| --- | --- | --- |"]
        for label, value, key in items:
            name, url = SOURCES[key]
            lines.append(f"| {label} | {value} | [{name}]({url}) |")
        return "\n".join(lines) + "\n"

    body = [
        "# ZeroFest 문제 보편성 근거",
        "",
        "심사 피드백 \"근거 자료가 특정 축제 사례 한두 개에 의존하고 있다\"에 대한 자료 정리다.",
        "이 문서와 `outputs/ZeroFest_문제_보편성_근거_보고서.docx`는 "
        "`scripts/build_problem_evidence_report.py` 하나에서 생성되므로 내용이 서로 어긋나지 않는다.",
        "",
        "제3자가 공표한 수치는 공표된 그대로 인용하며 이 저장소에서 재계산하지 않는다.",
        "",
        section("1. 문제가 발생하는 모집단", SCALE),
        section("2. 폐기 실태", REALITY),
        section("3. 통계 공백", GAP),
        "",
        "행사 폐기물은 국가 폐기물 통계의 별도 항목이 아니다. 축제가 개별 관리 단위로만",
        "취급되므로 전국 단위로 비교할 근거 자체가 생산되지 않는다. ZeroFest의 근거가",
        "개별 사례에 머문 것은 자료 조사의 부족이 아니라 이 범주가 집계되지 않기 때문이며,",
        "따라서 제품의 1차 기여는 예측 이전에 **측정 체계**다.",
        "",
        section("4. 정책 흐름", POLICY),
        "",
        "다회용기는 효과가 검증된 대책이지만 줄이는 대상은 **용기** 폐기물이다.",
        "부스가 재료를 과잉 준비해 **음식 자체**가 남는 문제를 다루는 대책은 확인되지 않았다.",
        "국회입법조사처가 제시한 '사전 감량' 방향에서 이 영역이 비어 있다.",
        "",
        section("5. 배경 통계", BACKGROUND),
        "## 6. 한계",
        "",
        "- 대학 축제의 음식 폐기량을 직접 집계한 국내 공식 통계는 확인되지 않았다.",
        "- 위 수치는 용기·일회용품 중심이므로 음식 폐기 규모의 직접 증거가 아니다.",
        "- 파일럿에서 부스별 잔여량을 실측하는 것이 이 공백을 메우는 첫 단계다.",
        "",
    ]
    MARKDOWN.write_text("\n".join(body))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_document(build_pages(fonts()), OUTPUT)
    write_markdown()
    print(f"Wrote {OUTPUT} (3 pages)")
    print(f"Wrote {MARKDOWN}")


if __name__ == "__main__":
    main()
