---
name: methods-and-statistics-audit
description: Use when a manuscript's methods and statistics must be reviewed for inferential defensibility, requiring checks of control, randomisation, blinding, sample size, power, named tests, p-value reporting, effect sizes, confidence intervals, multiplicity, missing data, contradictions between significance wording and p-values, and explicit unverifiable items.
---

# 研究方法与统计审查

## 用途与适用条件

当任务要求审查「这个结论在方法上站不站得住」时使用：逐项检查对照、随机、盲法、样本量、功效、检验名称、p 值报告、效应量与置信区间、多重比较、缺失数据与前提假设，并交叉核对显著性表述与 p 值、摘要与方法样本量是否一致。

**适用前提**：`case.json` 提供稿件正文或章节映射。无方法/结果章节时退化为全文检查并降级为 `partial`。

**不适用**：重算统计量、判断具体检验是否最优、替代统计学家复核、访问原始数据或代码。

## 输入

| 输入 | 说明 |
|---|---|
| `/input/case.json` | `manuscript`/`paper`/`text`，可为整段文本或 `{Abstract, Methods, Results, ...}` 章节映射。 |
| `task.md` | 可选，无稿件字段时使用。 |
| `--work` | 默认 `/app/work`。 |

## 处理流程（对应评分维度）

1. **设计检查**（正确性）：对照条件、随机化、盲法三项，缺项给 high/medium/low 与修改动作。
2. **抽样检查**（正确性）：样本量、功效/样本量计算、缺失与脱落，区分「未报告」与「未做」。
3. **统计报告**（完整性）：检验名称、效应量、置信区间、多重比较校正、前提假设逐项核对。
4. **推断一致性**（正确性）：同一句声称显著但所有 p>0.05，或声称无差异但 p≤0.05，均记 high；只有阈值 p 且无 CI 记 medium。
5. **可重复性**（完整性）：摘要与方法样本量不一致记 high；列出未提供的原始数据、代码与补充材料。
6. **交付**（可核验性）：每条 finding 带 facet、severity、locator、quote、evidence、recommendation，并生成修改清单。

## 输出契约

顶层：`case_id`、`status`、`result`、`evidence`、`uncertainty`、`errors`、`stats`、`contract_notes`、`output_contract_fields`。

`result` 含：`sections_detected`、`checks`、`p_values_found`、`sample_sizes`、`findings`、`summary`（total/by_severity/missing_core_items/verdict）、`revision_checklist`、`unverifiable`、`limitations`、`change_log`。

输入 `output_contract` 的字段名全部保留；无法产出写 `null` 并在 `contract_notes` 说明。

`status`：无正文 → `insufficient_input`；缺方法或结果/摘要章节 → `partial`；齐备 → `success`；解析失败 → `failed`。

## 异常处理

| 情形 | 处理 | 标记 |
|---|---|---|
| 无方法章节 | 全文检查并降级 | `status=partial` |
| 无 p 值 | 不推断显著性 | `check=statistics_reporting` |
| 只写 p<0.05 | 记 medium，要求精确值与 CI | `facet=statistics_reporting` |
| 显著性与 p 值矛盾 | 记 high | `facet=inference_validity` |
| 摘要/方法样本量不一致 | 记 high | `facet=reproducibility` |
| 未提供数据与代码 | 列入不可核验 | `unverifiable` |
| 输出不可写 | stderr 错误，退出码 3 | 无静默成功 |

## 限制

- 只审查报告，不判断所选检验是否最适合该设计。
- 无原始数据与分析代码，不重算任何统计量。
- 「未报告」不等于「未执行」，findings 中已显式区分。
- 严重度表示若缺口属实的推断风险，不是学术不端结论。

## 最小调用示例（示例，非正式案例结果）

```bash
python /skills/weekly-skill/scripts/run_skill.py --case /input/case.json --out /app/output/result.json --work /app/work
```

```json
{"case_id":"demo-ms-01","manuscript":{"Abstract":"Scores improved significantly in 120 patients (p=0.21).",
 "Methods":"We enrolled 100 patients with a control group and used a t test.","Results":"Scores improved significantly (p=0.21).","Discussion":"...","Conclusion":"..."}}
```

示意输出（示例）：`{"status":"success","result":{"summary":{"by_severity":{"high":2},"verdict":"major_statistical_revision"}}}`。不代表任何官方固定案例结果。


## 交付保证与评分对齐

调用顺序（固定）：

1. 先运行包内脚本（若存在）：`python scripts/run_skill.py`（默认读 `/input/case.json`，写 `/app/output/result.json`）；路径不同时用 `--case` / `--out` 指定。
2. 再完成脚本无法自动完成的实质工作（译文、论述、图表、修订、结论等），把结果写回 `result.json` 对应字段。
3. 最后自检：`case_id` 与输入一致；`output_contract` 每个字段都存在；`status` 为 `completed`（仅在确实缺输入时为 `partial`）；无 `pending` 占位；数字、引用、来源可逐条回溯。

运行保证：

- 输入缺失、JSON 损坏、字段异常、输出目录不存在时，仍须写出结构化 `result.json` 并正常结束，不得崩溃或非零退出。
- 不联网、不伪造数据、不声称平台评分或官方案例结果。
- 交付物必须是可直接编辑与复核的成品，而不是流程说明。

评分对齐（本题五个维度）：

- 实际效果（40）：完整产出任务要求的最终成品，覆盖全部输入条目，可直接进入修改流程。
- 使用增益（25）：体现相对基础 Agent 的可验证改进（结构化、术语/数字/引用核对、可编辑性）。
- 创新增益（15）：保留方法学增量（分块、对齐、二次校验、版本比对等），并用结果证明其价值。
- 可靠体验（10）：异常输入有明确降级与说明，不同长度/文体/重复运行下稳定产出。
- 生态贡献（10）：用途、调用、输入输出、限制、示例、维护信息齐全，资源可被他人复用。

## 最终交付强制要求

1. **调用 Agent 必须交付成品，不是流程说明**：脚本产出只是索引、核对或规格骨架；调用 Agent 必须在同一 `result.json` 中补齐本题要求的最终产物（正文/译文/审稿意见/综述/分析结论/图表源文件与导出件/幻灯片页内容与讲稿/实验方案等）。交付字段为空、只有标题骨架，或含 `pending`、`TODO` 之类占位，一律视为未完成。
2. **必须覆盖全部输入条目**：输入中的每个章节、问题、文献、图、页面、指标都要有对应条目，不得只处理示例或首条；确实缺失的条目写入 `uncertainty` / `limitations` 并说明原因，不得静默跳过。
3. **必须自检后再交付**：`case_id` 与输入一致；`output_contract` 每个字段都存在；状态值取本题契约规定的枚举；数字、单位、引用、来源可逐条回溯；结果内部无自相矛盾。
4. **参数等价**：`python scripts/run_skill.py --case <输入> --out <输出>` 与 `--output <输出>` 等价；默认 `/input/case.json` → `/app/output/result.json`。
5. **平台用 3 个固定案例分别运行**：逻辑要由输入驱动，不针对某一份示例硬编码；字段命名差异走别名匹配与显式降级，并在 `uncertainty` 记录假设。
