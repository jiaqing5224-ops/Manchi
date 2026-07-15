"""Create 4 demo orchestration rules via API for presentation.

Run: python -m scripts.create_demo_rules  (from backend dir)
or:  python backend/scripts/create_demo_rules.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from typing import Any

BASE = "http://127.0.0.1:8000"

DEMO_RULES: list[dict[str, Any]] = [
    {
        "name": "【演示1】本周会议雷达",
        "description": "闭环演示规则1：扫描本周会议邮件 → AI 提取会议时间/主题 → 导出 Excel + 自动创建会议准备任务",
        "source_config": {"type": "mail", "days_range": 7, "sender_filter": ""},
        "trigger_config": {"type": "manual"},
        "actions_config": [
            {"type": "ai_meeting_extract", "params": {}},
            {"type": "export_excel", "params": {"columns": ["subject", "start_time", "end_time", "duration_hours"], "filename": "会议报告.xlsx"}},
            {"type": "create_task", "params": {"title_field": "subject", "priority": "high"}},
        ],
        "is_active": True,
    },
    {
        "name": "【演示2】邮件智能分析报告",
        "description": "闭环演示规则2：邮件分类（紧急/常规/通知/垃圾）+ 整体摘要 → Markdown 分析报告",
        "source_config": {"type": "mail", "days_range": 3, "sender_filter": ""},
        "trigger_config": {"type": "manual"},
        "actions_config": [
            {"type": "ai_classify", "params": {"categories": ["紧急", "常规", "通知", "垃圾"]}},
            {"type": "ai_summarize", "params": {"max_length": 300}},
            {"type": "export_markdown", "params": {"filename": "邮件分析报告.md", "title": "邮件智能分析报告"}},
        ],
        "is_active": True,
    },
    {
        "name": "【演示3】紧急邮件转任务",
        "description": "闭环演示规则3：识别紧急邮件 → 提取待办事项 → 创建高优先级任务 → 通知",
        "source_config": {"type": "mail", "days_range": 2, "sender_filter": ""},
        "trigger_config": {"type": "manual"},
        "actions_config": [
            {"type": "ai_classify", "params": {"categories": ["紧急", "常规"]}},
            {"type": "ai_extract", "params": {"fields": ["action_item", "deadline"], "prompt_extra": "从紧急邮件中提取需要立即处理的待办事项和截止时间"}},
            {"type": "create_task", "params": {"title_field": "action_item", "priority": "high"}},
            {"type": "notify", "params": {"message": "已自动创建紧急任务，请前往任务中心查看"}},
        ],
        "is_active": True,
    },
    {
        "name": "【演示4】文本智能分析（非邮件源）",
        "description": "闭环演示规则4：自定义文本 → 分类 + 摘要 → Excel + 任务（展示非邮件输入源的闭环能力）",
        "source_config": {
            "type": "text",
            "content": (
                "本周项目进展：\n"
                "1. 用户认证模块开发完成，预计周三上线；\n"
                "2. 数据库迁移遇到性能瓶颈，需要 DBA 支持；\n"
                "3. 下周一开始进入集成测试阶段；\n"
                "4. 客户反馈新增需求：支持导出 PDF 格式报表。"
            ),
        },
        "trigger_config": {"type": "manual"},
        "actions_config": [
            {"type": "ai_classify", "params": {"categories": ["进度风险", "资源问题", "里程碑", "其他"]}},
            {"type": "ai_summarize", "params": {"max_length": 200}},
            {"type": "export_excel", "params": {"filename": "文本分析.xlsx"}},
            {"type": "create_task", "params": {"title_field": "tag", "priority": "medium"}},
        ],
        "is_active": True,
    },
]


def create_rule(rule: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(rule, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/rules",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    created = 0
    for rule in DEMO_RULES:
        try:
            result = create_rule(rule)
            print(f"[OK] Created rule #{result['id']}: {result['name']}")
            created += 1
        except Exception as e:
            print(f"[FAIL] {rule['name']} -> {e}", file=sys.stderr)
    print(f"\nDone: {created}/{len(DEMO_RULES)} demo rules created")
    return 0 if created == len(DEMO_RULES) else 1


if __name__ == "__main__":
    sys.exit(main())
