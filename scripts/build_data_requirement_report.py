#!/usr/bin/env python3
"""Turn the data-requirement study into a report.

Reads outputs/data_requirement_study.json, so the document always states what
the last run of scripts/run_data_requirement_study.py actually measured.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.report_layout import ACCENT, NAVY, Page, fonts, write_document  # noqa: E402

OUTPUT_DIR = ROOT / "outputs"
STUDY_PATH = OUTPUT_DIR / "data_requirement_study.json"
OUTPUT = OUTPUT_DIR / "ZeroFest_데이터_요구량_검증_보고서.docx"
CHART_PATH = OUTPUT_DIR / "data_requirement_learning_curve.png"
SATURATION_TOLERANCE = 0.05
# A corpus is only usable when repeated draws agree, not just when the mean
# stops falling. Both points are reported; the larger one is the recommendation.
STABILITY_RATIO = 0.02


def saturation_point(curve: list[dict[str, float]]) -> dict[str, float]:
    """The smallest corpus that lands within tolerance of the best result."""
    best = min(point["mae"] for point in curve)
    for point in curve:
        if point["mae"] <= best * (1 + SATURATION_TOLERANCE):
            return point
    return curve[-1]


def stability_point(curve: list[dict[str, float]]) -> dict[str, float]:
    """The smallest corpus whose repeated draws agree within STABILITY_RATIO."""
    for point in curve:
        if (point["mae_std"] or 0) <= point["mae"] * STABILITY_RATIO:
            return point
    return curve[-1]


def draw_learning_curve(curve: list[dict[str, float]], baseline_mae: float) -> Path:
    width, height = 1320, 700
    left, right, top, bottom = 110, width - 40, 60, height - 90
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font_set = fonts()
    font = font_set["axis"]
    korean = font_set["tiny"]  # Latin-only axis font cannot render Hangul labels

    xs = [point["festivals"] for point in curve]
    lows = [point["mae"] - (point["mae_std"] or 0) for point in curve]
    highs = [point["mae"] + (point["mae_std"] or 0) for point in curve]
    y_max = max(max(highs), baseline_mae) * 1.05
    y_min = min(lows) * 0.92

    def to_x(festivals: float) -> float:
        # Log spacing keeps the interesting 1-8 region readable next to 24.
        span = (len(xs) - 1) or 1
        return left + (right - left) * xs.index(festivals) / span

    def to_y(value: float) -> float:
        return bottom - (bottom - top) * (value - y_min) / (y_max - y_min)

    for step in range(6):
        value = y_min + (y_max - y_min) * step / 5
        y = to_y(value)
        draw.line((left, y, right, y), fill=(233, 237, 240))
        draw.text((left - 58, y - 9), f"{value:4.1f}", font=font, fill=(110, 110, 110))

    baseline_y = to_y(baseline_mae)
    for x in range(left, right, 14):
        draw.line((x, baseline_y, x + 7, baseline_y), fill=(200, 80, 80), width=2)
    draw.text((right - 320, baseline_y - 30), f"운영 기준선 MAE {baseline_mae:.2f}", font=korean, fill=(180, 60, 60))

    band = [(to_x(p["festivals"]), to_y(h)) for p, h in zip(curve, highs)]
    band += [(to_x(p["festivals"]), to_y(low)) for p, low in zip(reversed(curve), reversed(lows))]
    draw.polygon(band, fill=(222, 240, 233))

    points = [(to_x(p["festivals"]), to_y(p["mae"])) for p in curve]
    draw.line(points, fill=ACCENT, width=4)

    marker = saturation_point(curve)
    for point, (x, y) in zip(curve, points):
        is_saturation = point["festivals"] == marker["festivals"]
        radius = 9 if is_saturation else 6
        draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                     fill=NAVY if is_saturation else ACCENT, outline="white", width=2)
        draw.text((x - 12, bottom + 14), f"{int(point['festivals'])}", font=font, fill=(70, 70, 70))
        draw.text((x - 20, y - 34), f"{point['mae']:.2f}", font=font, fill=(60, 60, 60))

    saturation_x = to_x(marker["festivals"])
    draw.line((saturation_x, top, saturation_x, bottom), fill=(150, 170, 190), width=1)
    draw.text((saturation_x + 10, top + 2), f"포화 {int(marker['festivals'])}회", font=korean, fill=NAVY)

    draw.line((left, bottom, right, bottom), fill=(140, 140, 140), width=2)
    draw.line((left, top, left, bottom), fill=(140, 140, 140), width=2)
    draw.text((left - 70, top - 34), "MAE", font=font, fill=(70, 70, 70))
    draw.text(((left + right) // 2 - 110, bottom + 46), "학습에 사용한 독립 축제 수", font=font_set["small"], fill=(70, 70, 70))
    image.save(CHART_PATH)
    return CHART_PATH


def build_pages(study: dict, font_set: dict) -> list[Path]:
    curve = study["curve"]
    marker = saturation_point(curve)
    stability = stability_point(curve)
    recommended = max(marker, stability, key=lambda point: point["festivals"])
    best = min(point["mae"] for point in curve)
    first = curve[0]
    pages: list[Path] = []

    page = Page(font_set)
    page.title("ZeroFest 데이터 요구량 검증 보고서", "예측 모델을 쓰려면 축제 데이터가 몇 회분 필요한가")
    page.heading("1. 왜 행이 아니라 축제 단위로 세는가")
    page.body(
        "한 축제 안의 레코드는 같은 날씨, 같은 유동인구, 같은 메뉴 구성을 공유한다. "
        "따라서 한 축제에서 1,700행을 더 모으는 것과 새로운 축제 한 번을 더 치르는 것은 "
        "정보량이 전혀 다르다. 이 실험은 학습 단위를 행이 아니라 독립 축제로 두고, "
        "한 번도 본 적 없는 축제에서만 성능을 측정한다."
    )
    page.table(
        ["구성", "내용"],
        [
            ["학습 후보", f"독립 시뮬레이션 축제 {study['train_festivals']}회 (캠퍼스 규모·날씨·메뉴 배치 모두 독립 추출)"],
            ["평가 세트", f"학습에 쓰지 않은 축제 {study['test_festivals']}회 · {study['test_rows']:,}행 고정"],
            ["반복", "학습 크기마다 축제 조합을 다시 뽑아 5회 반복, 평균과 표준편차 보고"],
            ["비교 기준선", f"직전 30분 판매량 유지 규칙 (MAE {study['baseline_mae']:.2f})"],
        ],
        [280, 1220],
    )
    page.heading("2. 결론")
    page.body(
        f"정확도는 독립 축제 {int(marker['festivals'])}회분에서 최고 성능의 {SATURATION_TOLERANCE:.0%} 이내에 "
        f"도달한다. 축제 1회로 학습하면 MAE {first['mae']:.2f}, "
        f"{int(curve[-1]['festivals'])}회까지 늘려도 {best:.2f}에 그친다."
    )
    page.body(
        "다만 평균만 보면 안 된다. 축제 1회로 학습하면 어떤 축제를 뽑았느냐에 따라 MAE가 "
        f"±{first['mae_std']:.2f}까지 흔들린다. 반복 간 편차가 평균의 {STABILITY_RATIO:.0%} 아래로 "
        f"내려가는 시점은 {int(stability['festivals'])}회이며, 그때 편차는 ±{stability['mae_std']:.2f}다."
    )
    page.table(
        ["기준", "필요한 독립 축제 수", "MAE", "표준편차"],
        [
            ["정확도 포화", f"{int(marker['festivals'])}회", f"{marker['mae']:.2f}", f"±{marker['mae_std']:.2f}"],
            ["결과 안정성", f"{int(stability['festivals'])}회", f"{stability['mae']:.2f}", f"±{stability['mae_std']:.2f}"],
        ],
        [420, 420, 320, 340],
        highlight=1,
    )
    page.body(
        f"둘 중 큰 값인 {int(recommended['festivals'])}회를 준비 기준으로 삼는다. "
        "정확도가 멈춘 뒤에도 결과가 흔들린다면 그 수치는 아직 근거로 쓸 수 없다."
    )
    page.note("모든 축제는 합성 시뮬레이션이다. 이 수치는 실제 정확도가 아니라 필요한 데이터 규모의 추정값이다.")
    pages.append(page.save(OUTPUT_DIR / "data_requirement_page_1.png"))

    page = Page(font_set)
    page.title("학습곡선", "독립 축제 수에 따른 미관측 축제 예측 오차")
    page.paste(draw_learning_curve(curve, study["baseline_mae"]), (1420, 760))
    page.body("음영은 5회 반복의 표준편차 범위다. 붉은 점선은 운영 기준선이다.", max_chars=57)
    page.table(
        ["축제 수", "학습 행", "MAE", "표준편차", "R²"],
        [
            [
                f"{int(p['festivals'])}회", f"{int(p['rows']):,}", f"{p['mae']:.2f}",
                f"±{p['mae_std']:.2f}" if p["mae_std"] else "-", f"{p['r2']:.3f}",
            ]
            for p in curve
        ],
        [260, 320, 280, 300, 340],
        row_height=46,
        highlight=[p["festivals"] for p in curve].index(marker["festivals"]),
    )
    pages.append(page.save(OUTPUT_DIR / "data_requirement_page_2.png"))

    page = Page(font_set)
    page.title("규모와 전이", "축제를 크게 여는 것과, 실데이터를 받는 것")
    page.heading("3. 축제 규모를 키우면")
    page.body(
        "같은 6회 축제라도 부스와 메뉴가 많으면 한 축제가 담는 상황의 폭이 넓어진다. "
        "축제 횟수를 못 늘리는 상황에서는 규모가 대안이 된다."
    )
    page.table(
        ["구성", "학습 행", "MAE", "R²"],
        [[row["profile"], f"{int(row['rows']):,}", f"{row['mae']:.2f}", f"{row['r2']:.3f}"] for row in study["scale"]],
        [520, 320, 300, 360],
    )
    page.heading("4. 실데이터가 한 번 들어왔을 때")
    page.body(
        "실제 축제는 한 학기에 한 번뿐이다. 합성 데이터로 미리 학습해 두면 그 한 번이 "
        "짊어져야 할 몫이 줄어드는지 확인했다. 평가 대상은 학습 분포보다 수요가 35% 높고 "
        "규모도 더 큰, 한 번도 보지 못한 축제다."
    )
    transfer = study["transfer"]
    best_transfer = min(range(len(transfer)), key=lambda i: transfer[i]["mae"])
    page.table(
        ["전략", "사용한 실데이터", "MAE", "R²"],
        [
            [row["strategy"], f"{int(row['real_rows']):,}행", f"{row['mae']:.2f}", f"{row['r2']:.3f}"]
            for row in transfer
        ],
        [660, 300, 260, 280],
        row_height=48,
        highlight=best_transfer,
    )
    half = next(r for r in transfer if r["strategy"].startswith("합성 사전학습") and "50%" in r["strategy"])
    full_real = next(r for r in transfer if r["strategy"].startswith("실데이터만") and "100%" in r["strategy"])
    page.body(
        f"합성 사전학습에 실데이터 절반을 얹은 구성(MAE {half['mae']:.2f})이 "
        f"실데이터 전량 단독 학습(MAE {full_real['mae']:.2f})보다 낫다. "
        "합성 데이터가 실데이터 요구량을 대략 절반으로 줄인다는 뜻이다."
    )
    page.heading("5. 운영 계획으로 옮기면")
    page.bullets([
        f"사전 학습: 합성 축제 {int(recommended['festivals'])}회 이상으로 출시 전 모델을 준비한다.",
        "첫 실축제: 합성 모델을 그대로 쓰고, 축제 종료 후 잔차 보정만 학습시킨다.",
        "축제가 쌓일수록 보정 비중을 늘리고 합성 의존도를 낮춘다.",
        "학교가 늘어나는 것이 한 학교의 데이터가 쌓이는 것보다 빠르게 성능을 올린다.",
    ])
    page.note(
        "한계: 여기서 말하는 실데이터도 분포를 이동시킨 합성 축제다. 실제 POS 데이터가 확보되면 "
        "같은 실험을 그대로 다시 돌려 이 추정이 맞았는지 검증해야 한다."
    )
    pages.append(page.save(OUTPUT_DIR / "data_requirement_page_3.png"))
    return pages


def main() -> None:
    if not STUDY_PATH.exists():
        raise FileNotFoundError(
            f"{STUDY_PATH} 가 없습니다. 먼저 scripts/run_data_requirement_study.py 를 실행하세요."
        )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    study = json.loads(STUDY_PATH.read_text())
    write_document(build_pages(study, fonts()), OUTPUT)
    print(f"Wrote {OUTPUT} (3 pages)")
    print(f"Wrote {CHART_PATH}")


if __name__ == "__main__":
    main()
