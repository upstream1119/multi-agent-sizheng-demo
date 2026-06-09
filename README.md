# 多智能体协同教学问答助手

这是一个独立的 Streamlit 演示项目，用于展示受控流程式多智能体在固定知识库上的协同任务流：

- 检索智能体：从固定知识库中召回相关证据。
- 回答生成智能体：只依据已召回证据组织教学回答。
- 溯源审查智能体：核验回答是否具备 citation 支撑。
- 内容规范审查智能体：对表达边界和复核风险进行规则初筛。
- 任务完成报告：展示证据数量、引用数量与审查状态。

项目不调用外部大模型，不需要 API Key，也不依赖原大创仓库运行。

## 本地启动

```powershell
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Streamlit Community Cloud 部署

1. 将本项目推送到一个独立的 GitHub 公开仓库。
2. 登录 `https://share.streamlit.io`。
3. 选择 `Create app`。
4. 选择该 GitHub 仓库。
5. Branch 填写 `main`。
6. Main file path 填写 `streamlit_app.py`。
7. 点击 `Deploy`，等待生成公开网址。

## 使用建议

首次访问若应用正在唤醒，请稍候片刻。建议优先体验页面中的三个示例问题，再使用自由输入观察证据不足时的保守处理。

## 使用边界

本项目是阶段性教学演示系统。回答仅依据当前固定知识库生成，规则型审查不替代人工复核与专业判断。
