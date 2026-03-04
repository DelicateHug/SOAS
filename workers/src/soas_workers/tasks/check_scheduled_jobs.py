"""Periodic task to check and dispatch due scheduled jobs."""

import json
import logging
from datetime import datetime, timedelta, timezone

from celery import Celery
from croniter import croniter

from soas_workers.celery_app import app
from soas_workers.config import config
from soas_workers.db import get_connection

logger = logging.getLogger(__name__)


def _calendar_to_cron(cal_config: dict) -> str:
    """Convert a CalendarConfig dict to a cron expression (same logic as service)."""
    time_str = cal_config.get("time", "09:00")
    parts = time_str.split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0

    days_of_month = cal_config.get("days_of_month", [])
    months = cal_config.get("months", [])
    days_of_week = cal_config.get("days_of_week", [])

    dom = ",".join(str(d) for d in sorted(days_of_month)) if days_of_month else "*"
    mon = ",".join(str(m) for m in sorted(months)) if months else "*"
    # Convert Mon=0->1, ..., Sun=6->0
    cron_dow = [(d + 1) % 7 for d in days_of_week]
    dow = ",".join(str(d) for d in sorted(cron_dow)) if days_of_week else "*"

    return f"{minute} {hour} {dom} {mon} {dow}"


def _compute_next_run(job: dict) -> str | None:
    """Compute the next run time for a job. Returns ISO string or None."""
    now = datetime.now(timezone.utc)
    schedule_type = job["schedule_type"]

    if schedule_type == "interval":
        interval = job.get("interval_seconds")
        if not interval:
            return None
        return (now + timedelta(seconds=interval)).isoformat()

    # Resolve cron expression
    cron_expr = None
    if schedule_type == "cron":
        cron_expr = job.get("cron_expression")
    elif schedule_type == "calendar":
        cal = job.get("calendar_config")
        if cal:
            if isinstance(cal, str):
                cal = json.loads(cal)
            cron_expr = _calendar_to_cron(cal)

    if cron_expr and croniter.is_valid(cron_expr):
        cron = croniter(cron_expr, now)
        return cron.get_next(datetime).isoformat()

    return None


@app.task(name="soas.check_scheduled_jobs")
def check_scheduled_jobs():
    """Poll the database for due scheduled jobs and dispatch them."""
    now = datetime.now(timezone.utc)

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Find all due jobs
            cur.execute(
                """
                SELECT sj.*, a.status AS automation_status, a.script_path
                FROM scheduled_jobs sj
                JOIN automations a ON a.id = sj.automation_id
                WHERE sj.is_enabled = true
                  AND sj.next_run_at <= %s
                  AND (sj.start_date IS NULL OR sj.start_date <= %s)
                  AND (sj.end_date IS NULL OR sj.end_date > %s)
                """,
                (now, now, now),
            )
            due_jobs = cur.fetchall()

        if not due_jobs:
            return {"dispatched": 0}

        celery = Celery(broker=config.CELERY_BROKER_URL)
        dispatched = 0

        for job in due_jobs:
            # Skip if automation isn't active or has no compiled script
            if job["automation_status"] != "active":
                logger.warning(
                    "Skipping job %s: automation %s is %s",
                    job["id"], job["automation_id"], job["automation_status"],
                )
                continue
            if not job["script_path"]:
                logger.warning(
                    "Skipping job %s: automation %s has no compiled script",
                    job["id"], job["automation_id"],
                )
                continue

            parameters = job["parameters"] or {}
            if isinstance(parameters, str):
                parameters = json.loads(parameters)

            with conn.cursor() as cur:
                # Create ExecutionLog
                cur.execute(
                    """
                    INSERT INTO execution_logs (id, automation_id, triggered_by, parameters, status, created_at)
                    VALUES (gen_random_uuid(), %s::uuid, %s::uuid, %s::jsonb, 'pending', %s)
                    RETURNING id
                    """,
                    (
                        str(job["automation_id"]),
                        str(job["created_by"]),
                        json.dumps(parameters),
                        now,
                    ),
                )
                execution_row = cur.fetchone()
                execution_id = str(execution_row["id"])

                # Dispatch Celery task
                task = celery.send_task(
                    "soas.run_automation",
                    args=[execution_id, str(job["automation_id"]), parameters],
                )

                # Update execution with celery task id and status
                cur.execute(
                    """
                    UPDATE execution_logs
                    SET celery_task_id = %s, status = 'queued'
                    WHERE id = %s::uuid
                    """,
                    (task.id, execution_id),
                )

                # Update job: last_run_at, run_count, next_run_at
                next_run = _compute_next_run(dict(job))
                cur.execute(
                    """
                    UPDATE scheduled_jobs
                    SET last_run_at = %s,
                        run_count = run_count + 1,
                        next_run_at = %s
                    WHERE id = %s::uuid
                    """,
                    (now, next_run, str(job["id"])),
                )

            conn.commit()
            dispatched += 1
            logger.info(
                "Dispatched job %s (%s) -> execution %s",
                job["id"], job["name"], execution_id,
            )

    return {"dispatched": dispatched}
