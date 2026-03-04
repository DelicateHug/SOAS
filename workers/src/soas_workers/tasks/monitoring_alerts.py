"""Evaluate alert rules against current health metrics."""

import json
import uuid
from datetime import datetime, timezone

import redis
from sqlalchemy import create_engine, text

from soas_workers.celery_app import app
from soas_workers.config import config

CONDITION_OPS = {
    "gt": lambda v, t: v > t,
    "lt": lambda v, t: v < t,
    "gte": lambda v, t: v >= t,
    "lte": lambda v, t: v <= t,
    "eq": lambda v, t: v == t,
    "ne": lambda v, t: v != t,
}


@app.task(name="soas.monitoring_evaluate_alerts")
def monitoring_evaluate_alerts():
    """Check all enabled alert rules against current Redis health data.

    Runs every 30 seconds via Celery Beat (after health check).
    """
    r = redis.from_url(config.REDIS_URL)
    engine = create_engine(config.DATABASE_URL)

    # Load all enabled rules
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT id, name, component_type, metric_key, condition, threshold, severity, cooldown_seconds "
                "FROM alert_rules WHERE is_enabled = true"
            )
        )
        rules = result.fetchall()

    fired = 0
    for rule in rules:
        rule_id, name, comp_type, metric_key, condition, threshold, severity, cooldown = rule

        # Check cooldown
        cooldown_key = f"monitoring:alert:cooldown:{rule_id}"
        if r.exists(cooldown_key):
            continue

        # Get all health keys for this component type
        pattern = f"monitoring:health:{comp_type}:*"
        for key in r.keys(pattern):
            raw = r.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            metrics = data.get("metrics", {})
            value = metrics.get(metric_key)
            if value is None:
                continue

            op = CONDITION_OPS.get(condition)
            if op and op(float(value), float(threshold)):
                # Fire alert
                alert_id = str(uuid.uuid4())
                component_id = data.get("component_id", "unknown")
                title = f"{name}: {metric_key}={value} (threshold: {condition} {threshold})"
                message = (
                    f"Component {comp_type}/{component_id} triggered alert rule '{name}'. "
                    f"Metric '{metric_key}' value is {value}, threshold is {condition} {threshold}."
                )

                with engine.connect() as conn:
                    conn.execute(
                        text(
                            "INSERT INTO alerts (id, rule_id, component_type, component_id, "
                            "severity, title, message, metric_value, status) "
                            "VALUES (:id, :rule_id, :comp_type, :comp_id, :severity, "
                            ":title, :message, :metric_value, 'active')"
                        ),
                        {
                            "id": alert_id,
                            "rule_id": str(rule_id),
                            "comp_type": comp_type,
                            "comp_id": component_id,
                            "severity": severity,
                            "title": title,
                            "message": message,
                            "metric_value": float(value),
                        },
                    )
                    conn.commit()

                # Set cooldown
                r.setex(cooldown_key, cooldown, "1")

                # Publish to real-time channel
                r.publish(
                    "monitoring:alerts:channel",
                    json.dumps({
                        "type": "alert_fired",
                        "alert_id": alert_id,
                        "severity": severity,
                        "title": title,
                        "component_type": comp_type,
                        "component_id": component_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }),
                )
                fired += 1

    engine.dispose()
    return {"rules_checked": len(rules), "alerts_fired": fired}
