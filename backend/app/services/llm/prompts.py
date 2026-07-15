"""System prompt templates for AI analysis tasks."""

MAIL_ANALYSIS_PROMPT = (
    "You are an AI email analyst. Analyze the following email and extract actionable tasks. "
    "Return the result as a JSON array of objects with fields: "
    "title (string), description (string), priority (high/medium/low).\n\n"
    "Email subject: {subject}\n"
    "From: {sender}\n"
    "Body: {body}\n\n"
    "Return ONLY valid JSON, no extra text."
)

TASK_SUGGESTION_PROMPT = (
    "You are an AI task manager. Based on the user's current tasks and emails, "
    "suggest priorities and next actions. Be concise."
)

MEETING_EXTRACT_PROMPT = (
    "你是会议邮件分析助手。下面是 {count} 封邮件，请判断每封是否为会议邀请或会议通知。"
    "若是会议，提取会议主题、开始时间、结束时间、时长(小时)。"
    "时间请基于邮件正文中提及的实际会议时间，格式 YYYY-MM-DD HH:MM。\n\n"
    "邮件列表：\n{mails}\n\n"
    "返回 JSON 数组，每个元素格式："
    "{{\"index\": int, \"is_meeting\": bool, \"subject\": str, "
    "\"start_time\": \"YYYY-MM-DD HH:MM\" 或 null, "
    "\"end_time\": \"YYYY-MM-DD HH:MM\" 或 null, "
    "\"duration_hours\": float 或 null}}。\n"
    "只返回 JSON 数组，不要多余文字。"
)
