"""Mock 工具层：检索素材、生成脚本、成本估算、保存方案。

设计要点：
- 统一返回 ToolResult，便于 agent 观察和 Trace 记录。
- estimate_cost 返回 over_budget 标志，触发模型重规划。
- save_plan 幂等（按 idempotency_key）+ 可注入失败。
- 数据来自 data/，不接真实业务系统。
"""

import json
import os
from typing import Any

from .models import ToolResult

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _load(name: str) -> dict:
    with open(os.path.join(_DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


# 内存草稿库：幂等键 -> 草稿。进程内有效，模拟持久层。
_DRAFT_STORE: dict[str, dict] = {}
# 测试用失败注入：工具名 -> 剩余失败次数
_FAIL_INJECT: dict[str, int] = {}


def inject_failure(tool: str, times: int = 1) -> None:
    """测试/用例注入失败，agent 无需感知。"""
    _FAIL_INJECT[tool] = times


def reset() -> None:
    """重置内存状态，供测试隔离。"""
    _DRAFT_STORE.clear()
    _FAIL_INJECT.clear()


def _maybe_fail(tool: str) -> ToolResult | None:
    if _FAIL_INJECT.get(tool, 0) > 0:
        _FAIL_INJECT[tool] -= 1
        return ToolResult(ok=False, tool=tool, error=f"{tool} 模拟失败", summary="工具失败")
    return None


def search_material(topic: str) -> ToolResult:
    """按主题检索合成素材。"""
    if (f := _maybe_fail("search_material")):
        return f
    materials = _load("materials.json")["materials"]
    hits = [m for m in materials if topic and topic in m.get("topic", "")]
    if not hits:
        return ToolResult(ok=True, tool="search_material", data=[],
                          summary="无匹配素材")
    return ToolResult(ok=True, tool="search_material", data=hits,
                      summary=f"命中 {len(hits)} 条素材: {[m['id'] for m in hits]}")


def generate_script(material_id: str, plan_name: str = "") -> ToolResult:
    """基于素材生成脚本草案（合成）。"""
    if (f := _maybe_fail("generate_script")):
        return f
    materials = {m["id"]: m for m in _load("materials.json")["materials"]}
    m = materials.get(material_id)
    if not m:
        return ToolResult(ok=False, tool="generate_script", error=f"素材 {material_id} 不存在",
                          summary="素材缺失")
    script = f"【{m['topic']}】脚本草案：{m['content']}"
    return ToolResult(ok=True, tool="generate_script",
                      data={"material_id": material_id, "script": script, "plan": plan_name},
                      summary=f"已生成脚本，引用 {material_id}")


def estimate_cost(plan_name: str, budget: float | None) -> ToolResult:
    """估算方案成本，返回是否超预算。budget 缺失时无法判断。"""
    if (f := _maybe_fail("estimate_cost")):
        return f
    plans = _load("tool_costs.json")["plans"]
    plan = plans.get(plan_name)
    if not plan:
        return ToolResult(ok=False, tool="estimate_cost", error=f"未知方案 {plan_name}",
                          summary="方案不存在")
    cost = plan["estimated_cost"]
    if budget is None:
        return ToolResult(ok=True, tool="estimate_cost",
                          data={"plan": plan_name, "cost": cost, "over_budget": None},
                          summary=f"{plan_name} 估算 {cost}，预算缺失无法判断")
    over = cost > budget
    return ToolResult(ok=True, tool="estimate_cost",
                      data={"plan": plan_name, "cost": cost, "over_budget": over,
                            "budget": budget},
                      summary=f"{plan_name} 估算 {cost}，预算 {budget}，" +
                              ("超预算" if over else "在预算内"))


def save_plan(idempotency_key: str, plan_name: str, script: str = "") -> ToolResult:
    """保存草稿，幂等 + 可注入失败。不接真实发布。"""
    if (f := _maybe_fail("save_plan")):
        return f
    if idempotency_key in _DRAFT_STORE:
        existing = _DRAFT_STORE[idempotency_key]
        return ToolResult(ok=True, tool="save_plan", data=existing,
                          summary=f"已存在草稿 {existing['draft_id']}，未重复创建")
    draft_id = f"draft_{len(_DRAFT_STORE) + 1:03d}"
    draft = {"draft_id": draft_id, "plan": plan_name, "script": script,
             "idempotency_key": idempotency_key, "published": False}
    _DRAFT_STORE[idempotency_key] = draft
    return ToolResult(ok=True, tool="save_plan", data=draft,
                      summary=f"已保存草稿 {draft_id}（仅草稿，未发布）")


TOOL_REGISTRY: dict[str, Any] = {
    "search_material": search_material,
    "generate_script": generate_script,
    "estimate_cost": estimate_cost,
    "save_plan": save_plan,
}

TOOL_DESCRIPTIONS = {
    "search_material": "检索素材，参数 {topic}",
    "generate_script": "生成脚本，参数 {material_id, plan_name}",
    "estimate_cost": "估算方案成本，参数 {plan_name, budget}，返回 over_budget",
    "save_plan": "保存草稿，参数 {idempotency_key, plan_name, script}，幂等",
}