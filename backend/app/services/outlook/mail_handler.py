"""
Outlook mail scanner via pywin32 (Windows only).

Scans the local Outlook inbox and returns raw email data.
All functions gracefully degrade when Outlook is unavailable.
"""

from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class OutlookMail:
    """Represents a single scanned email."""

    def __init__(
        self,
        entry_id: str,
        subject: str,
        sender_name: str,
        sender_email: str,
        body_preview: str,
        received_at: Optional[datetime],
        full_body: str = "",
    ):
        self.entry_id = entry_id
        self.subject = subject
        self.sender_name = sender_name
        self.sender_email = sender_email
        self.body_preview = body_preview
        self.received_at = received_at
        self.full_body = full_body


def _parse_mail_item(mail_item: object) -> OutlookMail:
    """Extract an OutlookMail from a COM MailItem object."""
    sender = getattr(mail_item, "Sender", None)
    sender_name = getattr(sender, "Name", "") if sender else ""
    sender_email = (
        getattr(sender, "Address", "")
        if sender
        else (getattr(mail_item, "SenderEmailAddress", "") or "")
    )
    body = getattr(mail_item, "Body", "") or ""
    received = getattr(mail_item, "ReceivedTime", None)
    received_at: Optional[datetime] = None
    if received:
        received_at = datetime(
            received.year,
            received.month,
            received.day,
            received.hour,
            received.minute,
            received.second,
        )
    return OutlookMail(
        entry_id=str(getattr(mail_item, "EntryID", "")),
        subject=getattr(mail_item, "Subject", "") or "",
        sender_name=sender_name,
        sender_email=sender_email,
        body_preview=body[:200],
        received_at=received_at,
        full_body=body,
    )


def scan_inbox(max_items: int = 50) -> list[OutlookMail]:
    """
    Scan Outlook inbox and return recent emails.

    Raises RuntimeError if Outlook is unavailable or the COM call fails — the
    caller is expected to surface this error to the user instead of silently
    showing "0 mails scanned". Returns an empty list only when Outlook is
    reachable but the inbox genuinely has no mail items.
    """
    try:
        import win32com.client  # noqa: F811
        import pythoncom
    except ImportError as e:
        raise RuntimeError(f"pywin32 未安装，无法访问 Outlook: {e}") from e

    # COM must be initialized per-thread — FastAPI runs sync endpoints in a
    # thread pool, so each call may land on an uninitialized thread.
    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        inbox = outlook.GetDefaultFolder(6)  # olFolderInbox
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)

        results: list[OutlookMail] = []
        skipped_non_mail = 0
        item_errors = 0
        total = items.Count
        for i in range(min(max_items, total)):
            try:
                mail_item = items.Item(i + 1)
                if mail_item.Class != 43:  # olMail
                    skipped_non_mail += 1
                    continue
                results.append(_parse_mail_item(mail_item))
            except Exception as e:
                item_errors += 1
                logger.warning("Failed to parse mail item #%d: %s", i + 1, e)
                continue

        logger.info(
            "scan_inbox total=%d returned=%d skipped_non_mail=%d item_errors=%d",
            total, len(results), skipped_non_mail, item_errors,
        )
        return results

    except Exception as e:
        logger.error(f"Outlook scan failed: {e}", exc_info=True)
        raise RuntimeError(f"Outlook 扫描失败: {e}") from e
    finally:
        pythoncom.CoUninitialize()


def open_mail_in_outlook(entry_id: str) -> bool:
    """
    Open the original mail in the user's Outlook client via COM.

    Manchi caches only a preview/subject; the full message lives in Outlook,
    so "view original" should jump to Outlook rather than re-rendering it in-app.
    Raises RuntimeError if Outlook/COM is unavailable.
    """
    try:
        import win32com.client  # noqa: F811
        import pythoncom
    except ImportError as e:
        raise RuntimeError(f"pywin32 未安装，无法访问 Outlook: {e}") from e

    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        mail_item = outlook.GetItemFromID(entry_id)
        mail_item.Display()
        return True
    except Exception as e:
        logger.error("open_mail_in_outlook failed for %s: %s", entry_id, e)
        raise RuntimeError(f"无法在 Outlook 中打开邮件: {e}") from e
    finally:
        pythoncom.CoUninitialize()


def scan_inbox_range(
    start: datetime, end: datetime, max_items: int = 500
) -> list[OutlookMail]:
    """
    Scan Outlook inbox for emails received within [start, end].

    Pulls the most recent ``max_items`` emails (sorted by ReceivedTime desc)
    and filters by range on the Python side. This avoids Outlook Restrict's
    locale-dependent date parsing, which silently returns empty results on
    non-English Windows. Returns an empty list if Outlook is unavailable.
    """
    try:
        import win32com.client  # noqa: F811
        import pythoncom
    except ImportError:
        logger.warning("pywin32 not installed, cannot scan Outlook")
        return []

    # COM must be initialized per-thread — FastAPI runs sync endpoints in a
    # thread pool, so each call may land on an uninitialized thread.
    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        inbox = outlook.GetDefaultFolder(6)
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)

        results: list[OutlookMail] = []
        scanned = 0
        for i in range(min(max_items, items.Count)):
            try:
                mail_item = items.Item(i + 1)
                if mail_item.Class != 43:  # olMail
                    continue
                scanned += 1
                mail = _parse_mail_item(mail_item)
                # Stop early once we walk past the start of the range
                # (items are sorted desc by ReceivedTime).
                if mail.received_at and mail.received_at < start:
                    break
                if mail.received_at and start <= mail.received_at <= end:
                    results.append(mail)
            except Exception:
                continue

        logger.info(
            "scan_inbox_range scanned=%d matched=%d range=[%s,%s]",
            scanned, len(results), start.isoformat(), end.isoformat(),
        )
        return results

    except Exception as e:
        logger.error(f"Outlook range scan failed: {e}")
        return []
    finally:
        pythoncom.CoUninitialize()
