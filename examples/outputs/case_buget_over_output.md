# 运行结果：case_buget_over（mode=offline）

- 状态：`incomplete`
- 未完成原因：预算 5 不足，最低方案 plan_B 估算 8，缺口 3
- 费用合计：8

## 任务计划
1. search_material
2. generate_script
3. estimate_cost
4. estimate_cost

## 步骤状态
| 步骤 | 工具 | 成功 | 摘要 |
|---|---|---|---|
| 1 | search_material | True | 命中 2 条素材: ['M01', 'M02'] |
| 2 | generate_script | True | 已生成脚本，引用 M01 |
| 3 | estimate_cost | True | plan_A 估算 12，预算 5，超预算 |
| 4 | estimate_cost | True | plan_B 估算 8，预算 5，超预算 |

## 工具结果
- `search_material` ok=True：命中 2 条素材: ['M01', 'M02']
- `generate_script` ok=True：已生成脚本，引用 M01
- `estimate_cost` ok=True：plan_A 估算 12，预算 5，超预算
- `estimate_cost` ok=True：plan_B 估算 8，预算 5，超预算

## 已保存方案
（未保存）
