from src.generator.evidence_generator import generate_answer, generate_baseline_answer


def test_llm_mode_uses_provider_text(monkeypatch):
    class FakeProvider:
        name = "fake"

        def generate(self, prompt):
            from src.generator.llm_provider import LLMGenerationResult

            return LLMGenerationResult(
                text="这是由大模型基于证据生成的回答。",
                provider_name=self.name,
                status="success",
            )

    monkeypatch.setenv("DACHUANG_GENERATOR_MODE", "llm")
    monkeypatch.setenv("DACHUANG_LLM_PROVIDER", "fake")
    monkeypatch.setattr(
        "src.generator.evidence_generator.get_llm_provider",
        lambda provider_name: FakeProvider(),
    )

    result = generate_answer(
        "三湾改编有什么意义？",
        [
            {
                "id": "hit_001",
                "title": "三湾改编",
                "text": "三湾改编确立了支部建在连上的原则。",
                "source": "demo",
                "citation": {"doc": "中国共产党思想政治教育史", "section": "三湾改编", "page": 75},
                "hybrid_score": 0.9,
            }
        ],
    )

    assert result["answer"] == "这是由大模型基于证据生成的回答。"
    assert result["generator_mode"] == "llm"
    assert result["generator_provider"] == "fake"
    assert result["provider_status"] == "success"
    assert result["citations_used"]


def test_llm_mode_falls_back_to_template_when_provider_fails(monkeypatch):
    class FakeProvider:
        name = "fake"

        def generate(self, prompt):
            from src.generator.llm_provider import LLMGenerationResult

            return LLMGenerationResult(
                text="",
                provider_name=self.name,
                status="api_error",
            )

    monkeypatch.setenv("DACHUANG_GENERATOR_MODE", "llm")
    monkeypatch.setenv("DACHUANG_LLM_PROVIDER", "fake")
    monkeypatch.setattr(
        "src.generator.evidence_generator.get_llm_provider",
        lambda provider_name: FakeProvider(),
    )

    result = generate_answer(
        "三湾改编有什么意义？",
        [
            {
                "id": "hit_001",
                "title": "三湾改编",
                "text": "三湾改编确立了支部建在连上的原则。",
                "source": "demo",
                "citation": {"doc": "中国共产党思想政治教育史", "section": "三湾改编", "page": 75},
                "hybrid_score": 0.9,
            }
        ],
    )

    assert "三湾改编确立了支部建在连上的原则" in result["answer"]
    assert result["provider_status"] == "api_error"


def test_baseline_answer_uses_plain_model_prompt(monkeypatch):
    prompts = []

    class FakeProvider:
        name = "fake"

        def generate(self, prompt):
            from src.generator.llm_provider import LLMGenerationResult

            prompts.append(prompt)
            return LLMGenerationResult(
                text="这是普通大模型直接生成的回答。",
                provider_name=self.name,
                status="success",
            )

    monkeypatch.setenv("DACHUANG_LLM_PROVIDER", "fake")
    monkeypatch.setattr(
        "src.generator.evidence_generator.get_llm_provider",
        lambda provider_name: FakeProvider(),
    )

    result = generate_baseline_answer("三湾改编有什么意义？")

    assert result["answer"] == "这是普通大模型直接生成的回答。"
    assert result["provider_status"] == "success"
    assert "证据：" not in prompts[0]
    assert "不要声称使用了未提供的文献、引用或页码" in prompts[0]


def test_baseline_answer_reports_provider_failure(monkeypatch):
    class FakeProvider:
        name = "fake"

        def generate(self, prompt):
            from src.generator.llm_provider import LLMGenerationResult

            return LLMGenerationResult(
                text="",
                provider_name=self.name,
                status="api_error",
            )

    monkeypatch.setattr(
        "src.generator.evidence_generator.get_llm_provider",
        lambda provider_name: FakeProvider(),
    )

    result = generate_baseline_answer("三湾改编有什么意义？")

    assert "不会自动展示参考资料" in result["answer"]
    assert result["provider_status"] == "api_error"
