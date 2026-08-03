"""Verify the ai_analyze merge: registry, alias routing, empty short-circuit,
markdown render. LLM is mocked so no network/API needed."""

import sys
from pathlib import Path

# make backend importable
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import app.services.orchestrator.actions as actions
from app.services.orchestrator.engine import PipelineContext


class FakeCtx:
    """Minimal stand-in for PipelineContext for unit testing actions."""
    def __init__(self, data, source_type="text", source_content="", source_file_path="", db=None):
        self.current_data = data
        self.source_type = source_type
        self.source_content = source_content
        self.source_file_path = source_file_path
        self.db = db
        self.artifacts_dir = ""
        self.input_data = data
        self.steps = []


# --- mock the LLM client ---
import app.services.llm.client as llm_client

def fake_chat_complete(messages, prompt, temperature=0.0):
    # return shapes per call signature (we can't see mode here; use prompt text)
    if "信息提取助手" in prompt:
        return '[{"action_item": "回复客户", "deadline": "今天"}]'
    if "分类助手" in prompt:
        return '[{"index": 0, "tag": "紧急", "reason": "需立即处理"}]'
    if "摘要" in prompt:
        return "这是一份摘要内容。"
    return "{}"

llm_client.chat_complete = fake_chat_complete

# reset registry to make sure ai_analyze present
actions.refresh_components()

# 1. registry contains ai_analyze + 3 legacy aliases + others
expected = {"ai_analyze", "ai_extract", "ai_summarize", "ai_classify",
            "ai_meeting_extract", "create_task", "notify"}
assert expected.issubset(set(actions.ACTION_REGISTRY)), actions.ACTION_REGISTRY.keys()
assert "ai_analyze" in actions.COMPONENT_REGISTRY
print("[OK] registry has ai_analyze + legacy aliases")

# 2. empty-input short-circuit returns compatible empty shapes
for mode, expected_empty in [("extract", []), ("classify", []), ("summarize", "")]:
    ctx = FakeCtx("")
    out = actions._action_ai_analyze({"mode": mode}, ctx)
    assert out == expected_empty, (mode, out)
    assert any("输入为空" in s for s in ctx.steps), ctx.steps
print("[OK] empty-input short-circuit returns compatible shapes")

# 3. alias delegates route to ai_analyze with correct mode + raw output
ctx = FakeCtx("请回复客户，今天截止")
extract_out = actions._action_ai_extract({}, ctx)
assert isinstance(extract_out, list) and extract_out[0]["action_item"] == "回复客户", extract_out
ctx = FakeCtx("这是一封邮件")
classify_out = actions._action_ai_classify({"categories": ["紧急", "常规"]}, ctx)
assert isinstance(classify_out, list) and classify_out[0]["tag"] == "紧急", classify_out
ctx = FakeCtx("长文本内容")
sum_out = actions._action_ai_summarize({"max_length": 100}, ctx)
assert isinstance(sum_out, str) and "摘要" in sum_out, sum_out
print("[OK] legacy aliases route correctly and return raw shapes")

# 4. ai_analyze raw vs markdown
ctx = FakeCtx("一条内容")
raw = actions._action_ai_analyze({"mode": "extract"}, ctx)
assert isinstance(raw, list), raw
ctx = FakeCtx("一条内容")
md = actions._action_ai_analyze({"mode": "extract", "output_format": "markdown"}, ctx)
assert isinstance(md, str) and md.startswith("|") and "action_item" in md, md
print("[OK] ai_analyze markdown renders a table")
print(md)

# 5. seed templates resolve via the old type names (no ai_analyze needed)
from app.routers import rules
count = 0
for rule in rules.RULE_TEMPLATES:
    for step in rule.get("actions_config", []):
        t = step.get("type")
        if t in ("ai_extract", "ai_summarize", "ai_classify"):
            assert t in actions.COMPONENT_REGISTRY, t
            count += 1
print(f"[OK] {count} seed-template AI steps resolve via legacy type names")

print("\nALL CHECKS PASSED")
