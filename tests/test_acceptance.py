"""五项验收点：正常、缺信息、工具失败、预算超限、重复执行。"""
import pytest

from src import agent, tools


@pytest.fixture(autouse=True)
def _reset():
    tools.reset()
    yield
    tools.reset()


def _inputs(**kw):
    base = {"topic": "产品发布短视频", "budget": 10, "deadline": "2026-11-10"}
    base.update(kw)
    return base


def test_accept_normal():
    r = agent.run(_inputs(), mode="offline")
    assert r.status == "success" and r.saved_plan


def test_accept_missing_deadline():
    r = agent.run(_inputs(deadline=None), mode="offline")
    assert r.status == "incomplete" and "截止时间" in (r.incomplete_reason or "")


def test_accept_tool_failure():
    tools.inject_failure("save_plan", times=1)
    r = agent.run(_inputs(), mode="offline")
    assert r.status == "failed" and r.saved_plan is None


def test_accept_budget_over():
    """预算超限：所有方案均超预算，返回 incomplete 及缺口。"""
    r = agent.run(_inputs(budget=5), mode="offline")
    assert r.status == "incomplete"
    assert "预算" in (r.incomplete_reason or "")


def test_accept_duplicate_save_one_draft():
    r1 = agent.run(_inputs(), mode="offline")
    r2 = agent.run(_inputs(), mode="offline")
    assert r1.saved_plan["draft_id"] == r2.saved_plan["draft_id"]


def test_accept_tool_recovery():
    """加分项：工具失败后续跑，保留已成功步骤并用替代素材恢复。"""
    tools.inject_failure("generate_script", times=1)
    r = agent.run(_inputs(), mode="offline")
    gen_fail = [s for s in r.step_status if s["tool"] == "generate_script" and not s["ok"]]
    gen_ok = [s for s in r.step_status if s["tool"] == "generate_script" and s["ok"]]
    assert len(gen_fail) == 1
    assert len(gen_ok) == 1
    assert r.status == "success"
    assert r.saved_plan is not None