"""工具层单测：估算、幂等保存、失败注入、缺参数。"""
import pytest

from src import tools


@pytest.fixture(autouse=True)
def _reset():
    tools.reset()
    yield
    tools.reset()


def test_estimate_cost_over_budget():
    r = tools.estimate_cost("plan_A", budget=10)
    assert r.ok and r.data["cost"] == 12 and r.data["over_budget"] is True


def test_estimate_cost_within_budget():
    r = tools.estimate_cost("plan_B", budget=10)
    assert r.ok and r.data["cost"] == 8 and r.data["over_budget"] is False


def test_estimate_cost_missing_budget():
    r = tools.estimate_cost("plan_A", budget=None)
    assert r.ok and r.data["over_budget"] is None


def test_save_plan_idempotent():
    a = tools.save_plan("k1", "plan_B", "s")
    b = tools.save_plan("k1", "plan_B", "s")
    assert a.ok and b.ok
    assert a.data["draft_id"] == b.data["draft_id"]
    assert "未重复创建" in b.summary


def test_save_plan_failure_injected():
    tools.inject_failure("save_plan", times=1)
    r = tools.save_plan("k2", "plan_B", "s")
    assert r.ok is False and "模拟失败" in (r.error or "")


def test_search_material_hit_and_miss():
    hit = tools.search_material("发布")
    assert hit.ok and hit.data
    miss = tools.search_material("不存在的主题")
    assert miss.ok and miss.data == []


def test_generate_script_missing_material():
    r = tools.generate_script("M99", "plan_A")
    assert r.ok is False and "不存在" in (r.error or "")