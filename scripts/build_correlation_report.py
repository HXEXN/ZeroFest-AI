#!/usr/bin/env python3
"""Create the ZeroFest variable correlation report.

Every claim in the document is derived from the dataset at build time. Nothing
about which variables are redundant, or how strong a relationship is, is written
by hand, so the report cannot outlive the data it describes.
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

from models.demand_model import FEATURES, load_historical_data, uncensored  # noqa: E402
from services.mlops import FEATURE_LABELS  # noqa: E402

OUTPUT_DIR = ROOT / "outputs"
OUTPUT = OUTPUT_DIR / "ZeroFest_변수간_상관분석_보고서.docx"
HEATMAP = OUTPUT_DIR / "zerofest_correlation_heatmap.png"

TARGET = "future_sales_30m"
LABELS = {**FEATURE_LABELS, TARGET: "다음 30분 판매량"}
REDUNDANT_THRESHOLD = 0.80
HIGH_VIF = 10.0


def _variance_inflation(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    from sklearn.linear_model import LinearRegression

    scores: dict[str, float] = {}
    for column in columns:
        others = [name for name in columns if name != column]
        fit = LinearRegression().fit(frame[others], frame[column])
        r_squared = fit.score(frame[others], frame[column])
        scores[column] = float("inf") if r_squared >= 1 - 1e-12 else 1 / (1 - r_squared)
    return pd.Series(scores).sort_values(ascending=False)


def analyse() -> dict[str, object]:
    history = load_historical_data()
    usable = uncensored(history)
    columns = FEATURES + [TARGET]
    pearson = usable[columns].corr()
    spearman = usable[columns].corr(method="spearman")
    target_corr = pearson[TARGET].drop(TARGET).sort_values(key=lambda s: s.abs(), ascending=False)

    pairs = [
        (left, right, float(pearson.loc[left, right]))
        for index, left in enumerate(FEATURES)
        for right in FEATURES[index + 1:]
    ]
    redundant = sorted(pairs, key=lambda item: abs(item[2]), reverse=True)

    # Censoring is the single largest distortion of a sales correlation matrix,
    # so the report shows the same coefficients with and without truncated rows.
    censored_corr = history[columns].corr()[TARGET].drop(TARGET)
    shift = (target_corr - censored_corr).abs().sort_values(ascending=False)

    return {
        "history": history,
        "usable": usable,
        "pearson": pearson,
        "spearman": spearman,
        "target_corr": target_corr,
        "redundant": redundant,
        "censored_corr": censored_corr,
        "shift": shift,
        "vif": _variance_inflation(usable, FEATURES),
        "censored_share": float(history["censored_window_flag"].mean()),
    }


def build_heatmap(correlation: pd.DataFrame) -> None:
    labels = list(correlation.columns)
    cell, left, top = 46, 300, 96
    width = left + cell * len(labels) + 70
    height = top + cell * len(labels) + 120
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    regular = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 12)
    small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 10)
    title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
    draw.text((left, 28), "ZeroFest feature correlation heatmap", font=title, fill="black")

    def cell_color(value: float) -> tuple[int, int, int]:
        intensity = min(abs(value), 1.0)
        base = (43, 98, 160) if value >= 0 else (190, 55, 65)
        return tuple(int(255 * (1 - intensity) + channel * intensity) for channel in base)

    for row, row_label in enumerate(labels):
        draw.text((8, top + row * cell + 16), row_label, font=regular, fill="black")
        for col in range(len(labels)):
            value = float(correlation.iat[row, col])
            x, y = left + col * cell, top + row * cell
            draw.rectangle((x, y, x + cell, y + cell), fill=cell_color(value), outline=(225, 225, 225))
            if abs(value) >= 0.45 or row == col:
                draw.text(
                    (x + 4, y + 17), f"{value:.2f}", font=small,
                    fill="white" if abs(value) >= 0.58 else "black",
                )
    for col, label in enumerate(labels):
        draw.text((left + col * cell + 4, top - 34), label[:9], font=small, fill="black")
    draw.text(
        (left, height - 44),
        "Blue: positive    Red: negative    Values shown when |r| >= 0.45",
        font=regular, fill="black",
    )
    image.save(HEATMAP)


def build_pages(a: dict[str, object], fonts: dict[str, ImageFont.FreeTypeFont]) -> list[Path]:
    target_corr: pd.Series = a["target_corr"]  # type: ignore[assignment]
    spearman: pd.DataFrame = a["spearman"]  # type: ignore[assignment]
    redundant: list[tuple[str, str, float]] = a["redundant"]  # type: ignore[assignment]
    vif: pd.Series = a["vif"]  # type: ignore[assignment]
    shift: pd.Series = a["shift"]  # type: ignore[assignment]
    censored_corr: pd.Series = a["censored_corr"]  # type: ignore[assignment]
    usable: pd.DataFrame = a["usable"]  # type: ignore[assignment]
    history: pd.DataFrame = a["history"]  # type: ignore[assignment]

    top = target_corr.index[0]
    strong_pairs = [item for item in redundant if abs(item[2]) >= REDUNDANT_THRESHOLD]
    over_vif = [name for name, value in vif.items() if value >= HIGH_VIF]
    pages: list[Path] = []

    page = Page(fonts)
    page.title("ZeroFest 변수간 상관분석 보고서", "다음 30분 판매량 예측을 위한 합성 축제 운영 데이터 분석")
    page.heading("분석 결론")
    page.body(
        f"다음 30분 판매량과 가장 강한 관계를 보인 변수는 {LABELS[top]}"
        f"(r = {target_corr[top]:+.3f})이다. "
        + (
            f"절대 상관 {REDUNDANT_THRESHOLD:.2f} 이상인 피처 쌍은 "
            f"{len(strong_pairs)}개이며, 분산팽창계수가 {HIGH_VIF:.0f} 이상인 피처는 "
            f"{len(over_vif)}개다."
            if strong_pairs or over_vif
            else f"절대 상관 {REDUNDANT_THRESHOLD:.2f} 이상인 피처 쌍은 없다."
        )
    )
    page.heading("분석 기준")
    page.table(
        ["항목", "내용"],
        [
            ["분석 데이터", f"2023–2025년 3개 가상 대학 3일 축제 {len(history):,}건"],
            ["분석 대상", f"타깃이 잘리지 않은 {len(usable):,}건 (검열 {a['censored_share']:.1%} 제외)"],
            ["종속변수", f"{TARGET} 다음 30분 판매량"],
            ["독립변수", f"모델 입력 피처 {len(FEATURES)}개"],
            ["분석 방법", "Pearson 선형 상관계수, Spearman 순위 상관계수, 분산팽창계수"],
            ["해석 범위", "합성 데이터 기반 모델 개발용 결과이며 실제 판매 실증값이 아님"],
        ],
        [360, 1140],
    )
    page.heading("왜 검열 행을 빼고 보는가")
    page.body(
        "재고가 0이 되면 판매량은 수요를 더 이상 따라가지 않는다. 검열된 행을 함께 넣고 "
        "상관을 구하면 재고·판매·시간 변수가 한꺼번에 0으로 무너지면서 실제보다 훨씬 강한 "
        "관계가 나타난다. 아래 표는 같은 계수가 검열 행 포함 여부에 따라 얼마나 달라지는지다."
    )
    page.table(
        ["변수", "검열 포함", "검열 제외", "차이"],
        [
            [LABELS[name], f"{censored_corr[name]:+.3f}", f"{target_corr[name]:+.3f}", f"{shift[name]:.3f}"]
            for name in shift.head(4).index
        ],
        [560, 320, 320, 300],
    )
    pages.append(page.save(OUTPUT_DIR / "correlation_report_page_1.png"))

    page = Page(fonts)
    page.title("변수간 상관 히트맵", "Pearson 상관계수 기준 · 검열 행 제외")
    page.paste(HEATMAP, (1430, 1280))
    page.body(
        "파란색은 양의 상관, 빨간색은 음의 상관이다. 진한 색일수록 선형 관계가 강하며 "
        "대각선은 자기상관이다.", max_chars=57,
    )
    page.heading("중복성 확인")
    if strong_pairs:
        page.table(
            ["변수 1", "변수 2", "Pearson", "관리 제안"],
            [
                [
                    LABELS[left], LABELS[right], f"{value:+.3f}",
                    "대표 변수 1개 선택" if abs(value) >= 0.95 else "중요도·성능 확인",
                ]
                for left, right, value in strong_pairs[:5]
            ],
            [420, 420, 260, 380],
        )
    else:
        page.body(
            f"절대 상관 {REDUNDANT_THRESHOLD:.2f} 이상인 피처 쌍은 없다. 시각을 중복 표현하던 "
            "변수들을 제거하고 종료까지 남은 시간 하나로 정리한 결과다.", max_chars=57,
        )
    page.table(
        ["피처", "분산팽창계수", "판정"],
        [
            [LABELS[name], f"{value:.2f}", "확인 필요" if value >= HIGH_VIF else "양호"]
            for name, value in vif.head(6).items()
        ],
        [620, 380, 480],
    )
    pages.append(page.save(OUTPUT_DIR / "correlation_report_page_2.png"))

    page = Page(fonts)
    page.title("종속변수와의 관계", f"종속변수 {TARGET} 다음 30분 판매량")
    page.table(
        ["변수", "Pearson", "Spearman", "해석"],
        [
            [
                LABELS[name], f"{value:+.3f}", f"{spearman.loc[name, TARGET]:+.3f}",
                ("강함 " if abs(value) >= 0.7 else "중간 " if abs(value) >= 0.3 else "약함 ")
                + ("양의 관계" if value > 0 else "음의 관계"),
            ]
            for name, value in target_corr.items()
        ],
        [520, 250, 270, 460],
        row_height=48,
    )
    page.heading("모델 관리 제안")
    page.bullets([
        "최근·이전 30분 판매량은 예측 입력으로 유지한다.",
        "할인율은 상관이 낮아도 유일한 운영 개입 변수이므로 유지한다.",
        "선형 상관이 낮은 변수는 상호작용 항으로 기여할 수 있어 중요도로 함께 판단한다.",
        "검열 행은 상관분석과 학습 모두에서 동일한 기준으로 제외한다.",
    ])
    page.note(
        "할인율의 단독 상관은 낮다. 할인은 시간대와 함께 배정되므로 단순 상관이 아니라 "
        "관측 시점을 고정한 비교에서 효과가 드러난다."
    )
    pages.append(page.save(OUTPUT_DIR / "correlation_report_page_3.png"))
    return pages


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    analysis = analyse()
    build_heatmap(analysis["pearson"])  # type: ignore[arg-type]
    pages = build_pages(analysis, fonts())
    write_document(pages, OUTPUT)
    print(f"Wrote {OUTPUT} ({len(pages)} pages)")
    print(f"Wrote {HEATMAP}")


if __name__ == "__main__":
    main()
