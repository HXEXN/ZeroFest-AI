"""Create a correlation heatmap report from FreshRetailNet-50K evaluation data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "freshretailnet_eval.parquet"
OUTPUT_DIR = ROOT / "outputs"
OUTPUT = OUTPUT_DIR / "FreshRetailNet_상관분석_히트맵_보고서.docx"
HEATMAP = OUTPUT_DIR / "freshretailnet_correlation_heatmap.png"

COLUMNS = [
    "dt", "sale_amount", "stock_hour6_22_cnt", "discount", "holiday_flag", "activity_flag",
    "precpt", "avg_temperature", "avg_humidity", "avg_wind_level",
]
LABELS = {
    "sale_amount": "일 판매량",
    "stock_hour6_22_cnt": "재고 보유 시간",
    "discount": "할인율",
    "holiday_flag": "휴일 여부",
    "activity_flag": "행사 여부",
    "precpt": "강수량",
    "avg_temperature": "평균 기온",
    "avg_humidity": "평균 습도",
    "avg_wind_level": "평균 풍속",
    "weekday": "요일",
    "month": "월",
}


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("/System/Library/Fonts/Supplemental/AppleGothic.ttf", size)


def build_heatmap(corr: pd.DataFrame) -> None:
    labels = list(corr.columns)
    cell, left, top = 82, 330, 120
    width = left + cell * len(labels) + 70
    height = top + cell * len(labels) + 150
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((left, 35), "FreshRetailNet Pearson Correlation Heatmap", font=font(27), fill="black")

    def color(value: float) -> tuple[int, int, int]:
        intensity = abs(value)
        base = (43, 98, 160) if value >= 0 else (190, 55, 65)
        return tuple(int(255 * (1 - intensity) + channel * intensity) for channel in base)

    for row, name in enumerate(labels):
        draw.text((10, top + row * cell + 26), LABELS[name], font=font(19), fill="black")
        for col in range(len(labels)):
            value = float(corr.iat[row, col])
            x, y = left + col * cell, top + row * cell
            draw.rectangle((x, y, x + cell, y + cell), fill=color(value), outline=(220, 220, 220))
            text_color = "white" if abs(value) >= 0.55 else "black"
            draw.text((x + 17, y + 31), f"{value:.2f}", font=font(15), fill=text_color)
    for col, name in enumerate(labels):
        draw.text((left + col * cell + 7, top - 32), LABELS[name][:6], font=font(14), fill="black")
    draw.text((left, height - 48), "파란색은 양의 상관, 빨간색은 음의 상관", font=font(19), fill="black")
    image.save(HEATMAP)


def wrap(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, max_chars: int = 54, size: int = 25) -> int:
    words, line = text.split(" "), ""
    lines: list[str] = []
    for word in words:
        candidate = f"{line} {word}".strip()
        if len(candidate) > max_chars:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    for item in lines:
        draw.text((x, y), item, font=font(size), fill="black")
        y += size + 13
    return y


def draw_table(draw: ImageDraw.ImageDraw, y: int, headers: list[str], rows: list[list[str]], widths: list[int]) -> int:
    x, row_h = 110, 62
    for index, row in enumerate([headers] + rows):
        xx = x
        fill = (31, 78, 121) if index == 0 else ((243, 247, 250) if index % 2 == 0 else "white")
        color = "white" if index == 0 else "black"
        for value, column_width in zip(row, widths):
            draw.rectangle((xx, y, xx + column_width, y + row_h), fill=fill, outline=(210, 210, 210))
            draw.text((xx + 12, y + 18), value, font=font(19), fill=color)
            xx += column_width
        y += row_h
    return y


def report_pages(corr: pd.DataFrame, spearman: pd.DataFrame, count: int) -> list[Path]:
    width, height = 1700, 2200

    def page(title: str) -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        draw.text((110, 100), title, font=font(54), fill="black")
        draw.line((110, 180, 1590, 180), fill=(31, 78, 121), width=4)
        return image, draw, 245

    output: list[Path] = []
    target = corr["sale_amount"].drop("sale_amount").sort_values(key=lambda item: item.abs(), ascending=False)

    image, draw, y = page("FreshRetailNet 변수간 상관분석 보고서")
    draw.text((110, y), "Dingdong Inc FreshRetailNet-50K evaluation split 기반", font=font(25), fill=(80, 80, 80))
    y += 95
    draw.text((110, y), "분석 결론", font=font(32), fill="black")
    y += 60
    y = wrap(draw, f"총 {count:,}개 행을 분석한 결과, 일 판매량과 가장 큰 선형 관계를 보인 운영 변수는 할인율이다. Pearson 상관계수는 {target['discount']:+.3f}이며 음의 관계를 보였다. 재고 보유 시간은 {target['stock_hour6_22_cnt']:+.3f}로 약한 음의 관계를 보였다.", 110, y)
    y += 35
    draw.text((110, y), "분석 범위", font=font(32), fill="black")
    y += 60
    y = draw_table(draw, y, ["항목", "내용"], [
        ["데이터셋", "Dingdong-Inc FreshRetailNet-50K"],
        ["분석 분할", "evaluation split 350,000개 행"],
        ["종속변수", "sale_amount 일 판매량"],
        ["독립변수", "재고 할인 휴일 행사 강수량 기온 습도 풍속 날짜 파생 변수"],
        ["분석 방법", "Pearson 선형 상관계수와 Spearman 순위 상관계수"],
        ["제외 변수", "상품 및 카테고리 ID와 시간별 판매 배열은 해석 혼선을 막기 위해 제외"],
    ], [360, 1120])
    y += 70
    draw.text((110, y), "해석 주의", font=font(32), fill="black")
    y += 60
    wrap(draw, "상관계수는 변수 간 동시 변화의 정도를 보여줄 뿐 인과관계를 증명하지 않는다. 할인율의 음의 상관은 할인 적용 대상의 상품 특성, 재고 상태, 프로모션 시점이 함께 반영된 결과일 수 있다.", 110, y)
    p = OUTPUT_DIR / "freshretail_report_page_1.png"
    image.save(p)
    output.append(p)

    image, draw, y = page("운영 변수 상관 히트맵")
    draw.text((110, y), "Pearson 상관계수 기준", font=font(25), fill=(80, 80, 80))
    chart = Image.open(HEATMAP).convert("RGB")
    chart.thumbnail((1450, 1450))
    image.paste(chart, ((width - chart.width) // 2, y + 45))
    y += chart.height + 105
    y = wrap(draw, "할인율과 일 판매량의 음의 상관이 가장 뚜렷하다. 재고 보유 시간, 휴일 여부, 요일, 평균 습도는 약한 관계를 보인다. 기온과 평균 풍속, 행사 여부의 선형 상관은 매우 낮다.", 110, y)
    p = OUTPUT_DIR / "freshretail_report_page_2.png"
    image.save(p)
    output.append(p)

    image, draw, y = page("일 판매량과의 관계")
    draw.text((110, y), "종속변수 sale_amount 일 판매량", font=font(25), fill=(80, 80, 80))
    y += 75
    rows = []
    for key, value in target.items():
        direction = "양의 관계" if value > 0 else "음의 관계"
        rows.append([LABELS[key], f"{value:+.3f}", f"{spearman.loc[key, 'sale_amount']:+.3f}", direction])
    y = draw_table(draw, y, ["변수", "Pearson", "Spearman", "관계"], rows, [520, 300, 300, 400])
    y += 70
    draw.text((110, y), "ZeroFest 적용 제안", font=font(32), fill="black")
    y += 60
    for item in [
        "할인율은 판매량 예측에 포함하되 프로모션 대상 편향을 분리해 검증한다.",
        "재고 보유 시간과 재고 상태는 품절 및 수요 검열 가능성을 고려해 함께 관리한다.",
        "날씨 변수는 단독 상관보다 메뉴 유형과 시간대의 상호작용 변수로 확장해 검증한다.",
        "대학 축제 데이터 수집 시 판매 단위, 재고 상태, 할인 시점, 공연 시각을 같은 타임스탬프로 정렬한다.",
    ]:
        y = wrap(draw, "• " + item, 125, y, max_chars=58)
        y += 8
    p = OUTPUT_DIR / "freshretail_report_page_3.png"
    image.save(p)
    output.append(p)
    return output


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(DATA_PATH, columns=COLUMNS)
    timestamp = pd.to_datetime(frame.pop("dt"))
    frame["weekday"] = timestamp.dt.weekday
    frame["month"] = timestamp.dt.month
    corr = frame.corr(method="pearson", numeric_only=True)
    spearman = frame.corr(method="spearman", numeric_only=True)
    build_heatmap(corr)
    pages = report_pages(corr, spearman, len(frame))

    print("Created report page images", ", ".join(str(page) for page in pages))
    print(f"Rows analyzed {len(frame):,}")


if __name__ == "__main__":
    main()
