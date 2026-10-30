"""CLI 入口：运行内容任务规划 Agent，打印交付结果并归档到 examples/。

运行示例：
    python -m src.main --case case_normal --offline
    python -m src.main --case case_budget_over --offline --verbose
    python -m src.main --case case_normal --real   # 需配置 LLM_API_KEY
"""

import argparse
import json
import os
import sys
from typing import Any

from .agent import run
from .models import FinalReport

from . import tools

_ROOT = os.path.dirname(os.path.dirname(__file__))
_INPUT_DIR = os.path.join(_ROOT, "examples", "inputs")
_OUTPUT_DIR = os.path.join(_ROOT, "examples", "outputs")
_TRACE_DIR = os.path.join(_ROOT, "examples", "traces")


def _load_case(name: str) -> dict:
    path = os.path.join(_INPUT_DIR, f"{name}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"用例不存在: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _report_to_markdown(case: str, mode: str, report: FinalReport) -> str:
    lines = [f"# 运行结果：{case}（mode={mode}）", "", f"- 状态：`{report.status}`"]
    if report.incomplete_reason:
        lines.append(f"- 未完成原因：{report.incomplete_reason}")
    lines.append(f"- 费用合计：{report.total_cost}")
    lines.append("")
    lines.append("## 任务计划")
    lines += [f"{i+1}. {s}" for i, s in enumerate(report.task_plan)] or ["（无）"]
    lines.append("")
    lines.append("## 步骤状态")
    lines.append("| 步骤 | 工具 | 成功 | 摘要 |")
    lines.append("|---|---|---|---|")
    for s in report.step_status:
        lines.append(f"| {s['step_no']} | {s['tool']} | {s['ok']} | {s['summary']} |")
    lines.append("")
    lines.append("## 工具结果")
    for r in report.tool_results:
        lines.append(f"- `{r['tool']}` ok={r['ok']}：{r['summary']}")
    lines.append("")
    lines.append("## 已保存方案")
    if report.saved_plan:
        lines.append(f"- 草稿 ID：`{report.saved_plan.get('draft_id')}`")
        lines.append(f"- 方案：`{report.saved_plan.get('plan')}`")
        lines.append("- 仅草稿，未真实发布")
    else:
        lines.append("（未保存）")
    return "\n".join(lines) + "\n"


def _build_trace(case: str, mode: str, report: FinalReport) -> str:
    """JSONL 运行记录：步骤、工具参数、返回摘要、后续动作、决策依据。"""
    rows: list[str] = []
    for s in report.step_status:
        rows.append(json.dumps({
            "case": case, "mode": mode, "step_no": s["step_no"],
            "tool": s["tool"], "args": s.get("args", {}),
            "ok": s["ok"], "summary": s["summary"],
            "next_action": s.get("next_action", ""),
            "reason": s.get("reason", ""),
        }, ensure_ascii=False))
    return "\n".join(rows) + ("\n" if rows else "")


def _archive(case: str, mode: str, report: FinalReport) -> tuple[str, str]:
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    os.makedirs(_TRACE_DIR, exist_ok=True)
    out_path = os.path.join(_OUTPUT_DIR, f"{case}_output.md")
    trace_path = os.path.join(_TRACE_DIR, f"{case}.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(_report_to_markdown(case, mode, report))
    with open(trace_path, "w", encoding="utf-8") as f:
        f.write(_build_trace(case, mode, report))
    return out_path, trace_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="内容任务规划 Agent（第2题）")
    parser.add_argument("--case", required=True, help="examples/inputs 下的用例名，如 case_normal")
    parser.add_argument("--offline", action="store_true", help="使用离线 Mock 模型（默认）")
    parser.add_argument("--real", action="store_true", help="使用真实模型，需 LLM_API_KEY")
    parser.add_argument("--verbose", action="store_true", help="打印每步决策与工具结果")
    parser.add_argument("--no-archive", action="store_true", help="不写 examples/ 归档")
    args = parser.parse_args(argv)

    if args.real and args.offline:
        parser.error("--real 与 --offline 互斥")
    mode = "real" if args.real else "offline"

    try:
        raw = _load_case(args.case) # 读取case.json，得到raw 
    except FileNotFoundError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 2

    # 剥离用例中的控制字段，避免传入 agent 输入
    inject = raw.pop("_inject_failure", None)
    repeat = raw.pop("_repeat", 1)
    raw.pop("_force_plan", None)   # 目前仅用于说明，不改变 Mock 行为
    inputs = raw

    if inject:
        tools.inject_failure(inject["tool"], inject.get("times", 1))

    reports = []
    for _ in range(max(1, int(repeat))):
        try:
            reports.append(run(inputs, mode=mode, verbose=args.verbose))
        except Exception as e:
            print(f"[运行失败] {e}", file=sys.stderr)
            return 1

    report = reports[-1]
    if len(reports) > 1:
        ids = [r.saved_plan["draft_id"] for r in reports if r.saved_plan]
        print(f"[重复执行] 运行 {len(reports)} 次，草稿 ID：{ids}")

    print(_report_to_markdown(args.case, mode, report))
    if not args.no_archive:
        out_path, trace_path = _archive(args.case, mode, report)
        print(f"[归档] 输出: {out_path}")
        print(f"[归档] Trace: {trace_path}")
    return 0 if report.status in ("success", "incomplete") else 1


if __name__ == "__main__":
    raise SystemExit(main())