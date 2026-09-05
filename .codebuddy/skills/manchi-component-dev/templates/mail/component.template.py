"""Mail-capability component template (category: mail).

Reads Outlook mail via Windows COM (MAPI). Windows-only; no pip dependency,
but requires an installed + configured Outlook. Always import win32com
lazily inside run() so the component still loads on non-Windows machines.
"""
from __future__ import annotations

import json
from typing import Any


def run(params: dict, context: dict) -> Any:
    """Return a list of mail dicts: {subject, sender, received_at, body_preview}."""
    days_range = int(params.get("days_range") or 5)
    sender_filter = (params.get("sender_filter") or "").lower()

    try:
        import win32com.client
    except ImportError:
        raise RuntimeError("当前环境缺少 pywin32 / 非 Windows，无法读取 Outlook 邮件")

    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    inbox = outlook.GetDefaultFolder(9)  # 9 = olFolderInbox
    items = inbox.Items
    items.Sort("[ReceivedTime]", True)
    items.IncludeRecurrences = False

    from datetime import datetime, timedelta
    since = datetime.now() - timedelta(days=days_range)

    results: list[dict] = []
    for item in items:
        try:
            received = item.ReceivedTime
        except Exception:
            continue
        if received < since:
            continue
        sender = item.SenderName or (item.SenderEmailAddress or "")
        if sender_filter and sender_filter not in sender.lower():
            continue
        results.append({
            "subject": item.Subject or "",
            "sender": sender,
            "received_at": received.strftime("%Y-%m-%d %H:%M:%S"),
            "body_preview": (item.Body or "")[:500],
        })
    return results


if __name__ == "__main__":
    ctx = {"input_data": None, "artifacts_dir": "/tmp"}
    # 注意：自测需要 Windows + Outlook，否则会抛 RuntimeError
    try:
        print(json.dumps(run({"days_range": 3}, ctx), ensure_ascii=False, indent=2))
    except RuntimeError as e:
        print("跳过自测（非 Windows / 无 Outlook）:", e)
