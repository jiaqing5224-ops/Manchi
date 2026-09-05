"""Web-automation component template (category: web_automation).

Drives a browser to scrape a page or fill a form. Two modes:
  - "scripted": deterministic Playwright selectors (no LLM needed). Good for
    public demo forms with stable selectors.
  - "agent": LLM-driven browser-use Agent that follows a natural-language task
    per row (needs a configured LLM; use context["make_llm"]()).

The upstream input (input_requirement=table) is already a list[dict] of rows.
Never re-read a file for table/json inputs — iterate directly.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def run(params: dict, context: dict) -> Any:
    """params: 用户配置；context: 运行时上下文（见 spec.md）。"""
    target_url = params.get("target_url") or "https://demoqa.com/automation-practice-form"
    mode = params.get("mode") or "scripted"
    headless = bool(params.get("headless", True))

    rows = context.get("input_data")
    if not isinstance(rows, list):
        rows = [rows] if rows else []

    if mode == "agent":
        return _run_agent(rows, target_url, context)

    return _run_scripted(rows, target_url, headless, context)


def _run_agent(rows: list[dict], target_url: str, context: dict) -> list[dict]:
    """LLM-driven: one browser-use Agent per row, following NL instructions."""
    from browser_use import Agent, BrowserSession

    llm = context["make_llm"]()  # 返回 LangChain 模型（来自设置页 LLM 配置）

    results: list[dict] = []
    browser_session = BrowserSession(headless=True, disable_security=True)
    try:
        for idx, row in enumerate(rows, start=1):
            task = _build_row_task(row, target_url)
            agent = Agent(task=task, llm=llm, browser_session=browser_session)
            out = agent.run()
            ok = bool(getattr(out, "is_successful", lambda: True)())
            results.append({"row": idx, "status": "成功" if ok else "失败", "detail": str(out)[:200]})
    finally:
        browser_session.kill()
    return results


def _run_scripted(rows: list[dict], target_url: str, headless: bool, context: dict) -> list[dict]:
    """Deterministic Playwright fill using selectors. No LLM required."""
    from playwright.sync_api import sync_playwright

    results: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        for idx, row in enumerate(rows, start=1):
            try:
                page.goto(target_url, timeout=30000)
                # 示例：把每行的字段映射到表单控件（按需修改选择器）
                _fill_row(page, row)
                context.get("add_artifact", lambda _p: None)(f"{context.get('artifacts_dir', '/tmp')}/row_{idx}.png")
                results.append({"row": idx, "status": "成功"})
            except Exception as e:
                results.append({"row": idx, "status": f"失败: {e}"})
        browser.close()
    return results


def _fill_row(page, row: dict) -> None:
    """把一行 dict 填进表单。这里只是最小示例，请按目标表单的选择器改写。"""
    for key, value in row.items():
        if not value:
            continue
        sel = f"[name='{key}'], #field_{key}, textarea[name='{key}']"
        try:
            page.fill(sel, str(value), timeout=5000)
        except Exception:
            pass  # 控件不存在则跳过


def _build_row_task(row: dict, target_url: str) -> str:
    """构造给 browser-use Agent 的自然语言指令（参考 time_sheet_agent）。"""
    parts = [f"请打开页面 {target_url} 并填写一条记录："]
    for k, v in row.items():
        if v:
            parts.append(f"- {k}：{v}")
    parts.append("填完后保存；仅当保存成功才算完成。")
    return "\n".join(parts)


if __name__ == "__main__":
    sample = [
        {"name": "测试用户", "email": "test@example.com"},
        {"name": "张三", "email": "zhangsan@example.com"},
    ]
    ctx = {
        "input_data": sample,
        "artifacts_dir": "/tmp",
        "add_artifact": lambda p: None,  # 自测时不需要真实 LLM/浏览器
    }
    print(json.dumps(_run_scripted(sample, "https://demoqa.com/automation-practice-form", True, ctx), ensure_ascii=False, indent=2))
