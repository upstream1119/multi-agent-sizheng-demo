import argparse
import csv
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape


SYSTEM_LABELS = {
    "direct_llm": "普通大模型",
    "hybrid_rag": "混合检索增强",
    "hybrid_no_citation_enforcement": "去掉引用约束",
    "hybrid_no_source_review": "去掉溯源审查",
    "hybrid_no_policy_review": "去掉内容复核",
    "full_system": "完整多智能体系统",
}
SYSTEM_ORDER = list(SYSTEM_LABELS)
RISK_COLORS = {
    "direct_llm": "#9F2D2D",
    "hybrid_rag": "#C9974D",
    "hybrid_no_citation_enforcement": "#B85C4B",
    "hybrid_no_source_review": "#B85C4B",
    "hybrid_no_policy_review": "#B85C4B",
    "full_system": "#387A5A",
}
GROUNDING_COLORS = {
    system: "#5E8C6A" if system == "full_system" else "#7699B8"
    for system in SYSTEM_ORDER
}


def load_metrics(csv_path: Path) -> tuple[dict[str, dict[str, float]], int, int]:
    sums = defaultdict(lambda: defaultdict(float))
    counts = defaultdict(int)
    provider_success_count = 0

    with csv_path.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            system = row["system"]
            if system not in SYSTEM_LABELS:
                continue
            counts[system] += 1
            sums[system]["risky_output_rate"] += float(row["risky_output"])
            sums[system]["grounded_paragraph_rate"] += float(
                row["grounded_paragraph_rate"]
            )
            if row.get("provider_status") == "success":
                provider_success_count += 1

    missing = [system for system in SYSTEM_ORDER if not counts[system]]
    if missing:
        raise ValueError(f"Missing systems in evaluation CSV: {', '.join(missing)}")

    metrics = {
        system: {
            key: value / counts[system]
            for key, value in sums[system].items()
        }
        for system in SYSTEM_ORDER
    }
    question_count = max(counts.values())
    return metrics, question_count, provider_success_count


def _text(
    x: float,
    y: float,
    value: str,
    *,
    size: int = 16,
    weight: int = 400,
    fill: str = "#3D3935",
    anchor: str = "start",
) -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Microsoft YaHei, Noto Sans CJK SC, '
        f'sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}" '
        f'text-anchor="{anchor}">{escape(value)}</text>'
    )


def _render_panel(
    *,
    x: int,
    y: int,
    width: int,
    title: str,
    subtitle: str,
    metric_key: str,
    metrics: dict[str, dict[str, float]],
    colors: dict[str, str],
) -> list[str]:
    parts = [
        f'<rect x="{x}" y="{y}" width="{width}" height="485" rx="18" '
        'fill="#FFFFFF" stroke="#DED8CF"/>',
        _text(x + 28, y + 44, title, size=23, weight=700, fill="#4A211F"),
        _text(x + 28, y + 72, subtitle, size=14, fill="#77716B"),
    ]
    label_width = 148
    bar_x = x + label_width + 30
    bar_width = width - label_width - 78
    first_y = y + 119
    row_gap = 55

    for tick in range(0, 101, 25):
        tick_x = bar_x + bar_width * tick / 100
        parts.append(
            f'<line x1="{tick_x}" y1="{first_y - 18}" x2="{tick_x}" '
            f'y2="{first_y + row_gap * (len(SYSTEM_ORDER) - 1) + 18}" '
            'stroke="#EEEAE4" stroke-width="1"/>'
        )
        parts.append(_text(tick_x, y + 463, f"{tick}%", size=12, fill="#8B857E", anchor="middle"))

    for index, system in enumerate(SYSTEM_ORDER):
        value = metrics[system][metric_key]
        center_y = first_y + index * row_gap
        rendered_width = max(0, bar_width * value)
        parts.append(
            _text(
                bar_x - 14,
                center_y + 5,
                SYSTEM_LABELS[system],
                size=14,
                weight=600 if system == "full_system" else 400,
                anchor="end",
            )
        )
        parts.append(
            f'<rect x="{bar_x}" y="{center_y - 13}" width="{bar_width}" '
            'height="26" rx="8" fill="#F1EEE9"/>'
        )
        if rendered_width:
            parts.append(
                f'<rect x="{bar_x}" y="{center_y - 13}" width="{rendered_width:.1f}" '
                f'height="26" rx="8" fill="{colors[system]}"/>'
            )
        value_x = min(bar_x + rendered_width + 10, x + width - 18)
        anchor = "end" if value_x == x + width - 18 else "start"
        parts.append(
            _text(
                value_x,
                center_y + 5,
                f"{value * 100:.1f}%",
                size=14,
                weight=700,
                fill=colors[system],
                anchor=anchor,
            )
        )

    return parts


def render_svg(
    metrics: dict[str, dict[str, float]],
    question_count: int,
    provider_success_count: int,
    output_path: Path,
) -> None:
    width = 1360
    height = 720
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#F7F3EC"/>',
        _text(60, 68, "多智能体机制消融实验", size=34, weight=700, fill="#4A211F"),
        _text(
            60,
            101,
            "比较完整系统与去模块版本，观察来源约束和审查门控的实际作用",
            size=17,
            fill="#6E6862",
        ),
    ]
    parts.extend(
        _render_panel(
            x=50,
            y=135,
            width=615,
            title="风险输出率",
            subtitle="存在未审查或未通过风险时仍输出，越低越好",
            metric_key="risky_output_rate",
            metrics=metrics,
            colors=RISK_COLORS,
        )
    )
    parts.extend(
        _render_panel(
            x=695,
            y=135,
            width=615,
            title="回答可溯源率",
            subtitle="回答段落带有效资料编号的平均比例，越高越好",
            metric_key="grounded_paragraph_rate",
            metrics=metrics,
            colors=GROUNDING_COLORS,
        )
    )
    parts.extend(
        [
            _text(
                60,
                657,
                f"评测设置：{question_count} 道课程问答题，GLM-4.5-Air；"
                f"图中所选系统共 {provider_success_count} 次调用成功。",
                size=14,
                fill="#6E6862",
            ),
            _text(
                60,
                684,
                "说明：自动指标用于初步机制验证，不替代教师或专家盲评，也不代表统计显著性结论。",
                size=13,
                fill="#8A514B",
            ),
            "</svg>",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot GLM ablation evaluation results.")
    parser.add_argument("--input", required=True, help="Path to demo_eval CSV.")
    parser.add_argument(
        "--output",
        default="figures/ablation_results_glm.svg",
        help="SVG output path.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    metrics, question_count, provider_success_count = load_metrics(input_path)
    render_svg(metrics, question_count, provider_success_count, output_path)
    print(f"SVG: {output_path.resolve()}")


if __name__ == "__main__":
    main()
