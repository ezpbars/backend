import secrets
from itgs import Itgs
import os
import time


async def up(itgs: Itgs) -> None:
    conn = await itgs.conn()
    cursor = conn.cursor("strong")
    await cursor.execute(
        """INSERT INTO pricing_plans(
            uid,
            slug,
            stripe_price_id,
            unit_amount
        ) VALUES (?, ?, ?, ?)""",
        ("ep_pp_" + secrets.token_urlsafe(16), "free", "example", 1000),
    )
    await cursor.execute(
        """INSERT INTO pricing_plan_tiers(
            uid,
            pricing_plan_id,
            position,
            units,
            unit_price_cents
        ) SELECT
            ?,
            pricing_plans.id,
            ?,
            ?,
            ?
        FROM pricing_plans
        WHERE pricing_plans.slug = ?""",
        ("ep_pp_t_" + secrets.token_urlsafe(16), 0, None, 0, "free"),
    )
    await cursor.execute(
        """INSERT INTO users(
            sub,
            created_at
        ) VALUES (?, ?)
        """,
        (os.environ["EXAMPLE_USER_SUB"], time.time()),
    )
    await cursor.execute(
        """INSERT INTO user_pricing_plans(
            uid,
            user_id,
            pricing_plan_id
        ) SELECT 
            ?,
            users.id,
            pricing_plans.id
        FROM users
        JOIN pricing_plans ON pricing_plans.slug = ?
        WHERE
            users.sub = ?""",
        (
            "ep_upp_" + secrets.token_urlsafe(16),
            "free",
            os.environ["EXAMPLE_USER_SUB"],
        ),
    )
