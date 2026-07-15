from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings


engine = create_engine(
    f"sqlite:///{settings.database_path}",
    connect_args={"check_same_thread": False},  # SQLite shared mode
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yield a DB session, auto-close on finish."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_rules_table() -> None:
    """Add new pipeline columns to the legacy rules table if needed.

    The old schema had trigger_type/action_type/config (strings); the new
    schema uses source_config/trigger_config/actions_config (JSON) plus
    last_run_at/last_run_status/last_run_message/updated_at. SQLite cannot
    drop columns, so we keep the old ones around (ignored by the ORM) and
    ADD COLUMN the new ones. Existing rows are migrated via ORM (Python-side)
    to avoid raw-SQL colon-escaping issues with JSON literals.
    """
    insp = inspect(engine)
    if "rules" not in insp.get_table_names():
        return  # table will be created fresh by create_all

    existing = {c["name"] for c in insp.get_columns("rules")}
    has_legacy = "trigger_type" in existing or "action_type" in existing

    # Add missing columns. Defaults use SQL literals (no colons to worry about).
    new_columns: list[tuple[str, str, str]] = [
        ("source_config", "TEXT", "'{}'"),
        ("trigger_config", "TEXT", "'{\"type\": \"manual\"}'"),
        ("actions_config", "TEXT", "'[]'"),
        ("updated_at", "DATETIME", "NULL"),
        ("last_run_at", "DATETIME", "NULL"),
        ("last_run_status", "VARCHAR(32)", "NULL"),
        ("last_run_message", "TEXT", "NULL"),
    ]
    with engine.begin() as conn:
        for col_name, col_type, default in new_columns:
            if col_name not in existing:
                conn.execute(
                    text(f"ALTER TABLE rules ADD COLUMN {col_name} {col_type} DEFAULT {default}")
                )

    # Migrate legacy rows via ORM (Python-side) to avoid SQL string escaping.
    if not has_legacy:
        return
    import json
    from sqlalchemy import text as sa_text
    with SessionLocal() as db:
        rows = db.execute(sa_text("SELECT id, trigger_type, action_type, source_config, trigger_config, actions_config FROM rules")).fetchall()
        for row in rows:
            rid = row[0]
            t_type = row[1] or "manual"
            a_type = row[2] or ""
            src_cfg = row[3]
            trg_cfg = row[4]
            act_cfg = row[5]

            updates: dict[str, str] = {}
            if not src_cfg or src_cfg == "{}":
                updates["source_config"] = json.dumps({"type": "text", "content": ""}, ensure_ascii=False)
            if not trg_cfg:
                if t_type == "schedule":
                    updates["trigger_config"] = json.dumps({"type": "schedule", "cron": "0 9 * * *"}, ensure_ascii=False)
                else:
                    updates["trigger_config"] = json.dumps({"type": "manual"}, ensure_ascii=False)
            if not act_cfg or act_cfg == "[]":
                if a_type == "classify":
                    updates["actions_config"] = json.dumps([{"type": "ai_classify", "params": {"categories": ["紧急", "常规", "垃圾"]}}], ensure_ascii=False)
                elif a_type == "summarize":
                    updates["actions_config"] = json.dumps([{"type": "ai_summarize", "params": {"max_length": 300}}], ensure_ascii=False)
                elif a_type == "notify":
                    updates["actions_config"] = json.dumps([{"type": "notify", "params": {"channel": "tray"}}], ensure_ascii=False)
                else:
                    updates["actions_config"] = "[]"

            if updates:
                set_clause = ", ".join(f"{k} = :v_{k}" for k in updates)
                params = {f"v_{k}": v for k, v in updates.items()}
                params["rid"] = rid
                db.execute(sa_text(f"UPDATE rules SET {set_clause} WHERE id = :rid"), params)
        db.commit()


def _migrate_tasks_table() -> None:
    """Add source_type / source_text / source_file_path to legacy tasks table.

    Existing rows keep their source_mail_id; source_type is left NULL so the
    app can infer "mail" from source_mail_id at read time, preserving
    backward compatibility with rows created before multi-source support.
    """
    insp = inspect(engine)
    if "tasks" not in insp.get_table_names():
        return  # table will be created fresh by create_all

    existing = {c["name"] for c in insp.get_columns("tasks")}
    new_columns: list[tuple[str, str, str]] = [
        ("source_type", "VARCHAR(16)", "NULL"),
        ("source_text", "TEXT", "NULL"),
        ("source_file_path", "VARCHAR(512)", "NULL"),
        ("group_id", "INTEGER", "NULL"),
    ]
    with engine.begin() as conn:
        for col_name, col_type, default in new_columns:
            if col_name not in existing:
                conn.execute(
                    text(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_type} DEFAULT {default}")
                )


def init_db():
    """Create all tables (idempotent) and run lightweight migrations."""
    import app.models.task  # noqa: F401
    import app.models.mail  # noqa: F401
    import app.models.rule  # noqa: F401
    import app.models.conversation  # noqa: F401
    import app.models.setting  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_rules_table()
    _migrate_tasks_table()
