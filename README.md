# 多智能体思政可信问答演示系统

这是一个独立的 Streamlit 可信问答项目，用于展示固定知识库上的：

- 证据检索
- 基于证据的回答生成
- Citation 来源核验
- 内容规范规则初筛
- 多阶段协同处理轨迹

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
