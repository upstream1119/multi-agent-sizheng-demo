# 多智能体协同教学问答助手

这是一个独立的 Streamlit 演示项目，用于展示受控流程式多智能体在固定知识库上的协同任务流：

- 检索智能体：从固定知识库中召回相关证据。
- 回答生成智能体：只依据已召回证据调用 GLM-4.5-Air 组织教学回答。
- 溯源审查智能体：核验回答是否具备 citation 支撑。
- 内容规范审查智能体：对表达边界和复核风险进行规则初筛。
- 任务完成报告：展示证据数量、引用数量与审查状态。

项目默认使用固定知识库检索，并通过 GLM-4.5-Air API 增强回答生成。若 API Key 未配置或接口暂时不可用，系统会自动回退到本地模板回答，保证页面可展示。

## 本地启动

```powershell
pip install -r requirements.txt
$env:ZHIPUAI_API_KEY="你的智谱 API Key"
streamlit run streamlit_app.py
```

## Streamlit Community Cloud 部署

1. 将本项目推送到一个独立的 GitHub 公开仓库。
2. 登录 `https://share.streamlit.io`。
3. 选择 `Create app`。
4. 选择该 GitHub 仓库。
5. Branch 填写 `main`。
6. Main file path 填写 `streamlit_app.py`。
7. 展开 Advanced settings，在 Secrets 中填写：

```toml
ZHIPUAI_API_KEY = "你的智谱 API Key"
```

8. 点击 `Deploy`，等待生成公开网址。

## 使用建议

首次访问若应用正在唤醒，请稍候片刻。建议优先体验页面中的三个示例问题，再使用自由输入观察证据不足时的保守处理。

## 最小评测

项目内置一个小规模评测入口，用于比较普通大模型、单路检索、混合检索和完整多智能体流程。

```powershell
$env:ZHIPUAI_API_KEY="你的智谱 API Key"  # 可选；未配置时会使用本地兜底回答
python -m src.evaluation.demo_eval --limit 10
```

结果会输出到 `outputs/eval/`：

- `demo_eval_时间戳.csv`：逐题逐系统指标，预留专家盲评打分列。
- `demo_eval_时间戳_summary.json`：各系统自动指标均值。

当前自动指标包括 `retrieval_hit_at_3`、`citation_count`、`source_pass`、`policy_pass`、`final_approved`、`unsupported_risk` 和 `answer_length`。这些指标用于 smoke test 和消融设计，不等同于最终专家评测结论。

当前评测包含以下 baseline 与消融设置：

| System | 含义 |
|---|---|
| `direct_llm` | 普通大模型直接回答，不检索、不引用、不审查。 |
| `vector_rag` | 仅使用向量检索证据后生成回答。 |
| `graph_rag` | 仅使用图谱实体检索证据后生成回答。 |
| `hybrid_rag` | 融合向量检索与图谱检索，并进行引用、溯源与内容复核。 |
| `hybrid_no_citation_enforcement` | 去掉回答中的 citation 强制标注，用于观察可溯源性下降。 |
| `hybrid_no_source_review` | 去掉溯源审查智能体，用于观察未核验来源时的输出风险。 |
| `hybrid_no_policy_review` | 去掉内容规范审查智能体，用于观察规则复核的贡献。 |
| `hybrid_no_trust_gate` | 去掉最终 Trust Gate，用于观察有风险结果是否会被放行。 |
| `full_system` | 完整受控多智能体流程：检索、生成、溯源审查、内容复核和最终门控。 |

新增指标 `risky_output_rate` 表示系统在存在未审查或未通过风险时仍然输出的比例，主要用于观察审查与门控模块的消融效果。

若需要组织人工盲评，可参考 `eval/expert_rubric.md`。CSV 中已预留 `expert_fact_score`、`expert_style_score`、`expert_policy_score` 和 `expert_preference` 列，可直接交由老师或专家补评分。

## 使用边界

本项目是阶段性教学演示系统。回答仅依据当前固定知识库生成，规则型审查不替代人工复核与专业判断。
