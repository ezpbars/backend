from itgs import Itgs
import secrets


async def up(itgs: Itgs) -> None:
    conn = await itgs.conn()
    cursor = conn.cursor("strong")
    await cursor.execute(
        """
        CREATE TABLE pricing_plans(
            id INTEGER PRIMARY KEY,
            uid TEXT UNIQUE NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            stripe_price_id TEXT UNIQUE NOT NULL,
            unit_amount INTEGER NOT NULL
        )
        """
    )
    await cursor.execute(
        """
        CREATE TABLE pricing_plan_tiers(
            id INTEGER PRIMARY KEY,
            uid TEXT UNIQUE NOT NULL,
            pricing_plan_id INTEGER NOT NULL REFERENCES pricing_plans(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            units INTEGER NULL,
            unit_price_cents INTEGER NOT NULL
        )
        """
    )
    await cursor.execute(
        """CREATE UNIQUE INDEX pricing_plan_tiers_pricing_plan_id_position ON pricing_plan_tiers(pricing_plan_id, position)"""
    )
    await cursor.execute(
        """
        CREATE TABLE user_pricing_plans(
            id INTEGER PRIMARY KEY,
            uid TEXT UNIQUE NOT NULL,
            user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            pricing_plan_id INTEGER NOT NULL REFERENCES pricing_plans(id) ON DELETE CASCADE
        )
        """
    )
    await cursor.execute(
        """CREATE INDEX user_pricing_plans_pricing_plan_id ON user_pricing_plans(pricing_plan_id)"""
    )
    await cursor.execute(
        """
        CREATE TABLE stripe_invoices(
            id INTEGER PRIMARY KEY,
            uid TEXT UNIQUE NOT NULL,
            stripe_id TEXT UNIQUE NOT NULL,
            hosted_invoice_url TEXT NOT NULL,
            total INTEGER NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    await cursor.execute(
        """
        CREATE TABLE user_usages(
            id INTEGER PRIMARY KEY,
            uid TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            traces INTEGER NOT NULL,
            period_started_at REAL NOT NULL,
            period_ended_at REAL NOT NULL,
            stripe_invoice_id INTEGER NULL REFERENCES stripe_invoices(id) ON DELETE SET NULL
        )
        """
    )
    await cursor.execute(
        "CREATE UNIQUE INDEX user_usages_user_id_period_started_at ON user_usages(user_id, period_started_at)"
    )
    await cursor.execute(
        "CREATE INDEX user_usages_stripe_invoice_id ON user_usages(stripe_invoice_id);"
    )
    await cursor.execute(
        """
        INSERT INTO pricing_plans(
            uid,
            slug,
            stripe_price_id,
            unit_amount
        )
        VALUES (
            ?, ?, ?, ?
        )
        """,
        ("ep_pp_" + secrets.token_urlsafe(16), "public", "test", 1000),
    )
    await cursor.execute(
        """
        INSERT INTO pricing_plan_tiers(
            uid,
            pricing_plan_id,
            position,
            units,
            unit_price_cents
        )
        VALUES (?, ?, ?, ?, ?), (?, ?, ?, ?, ?), (?, ?, ?, ?, ?), (?, ?, ?, ?, ?), (?, ?, ?, ?, ?)
        """,
        (
            "ep_pp_t_" + secrets.token_urlsafe(16),
            1,
            0,
            5,
            0,
            "ep_pp_t_" + secrets.token_urlsafe(16),
            1,
            1,
            95,
            75,
            "ep_pp_t_" + secrets.token_urlsafe(16),
            1,
            2,
            900,
            50,
            "ep_pp_t_" + secrets.token_urlsafe(16),
            1,
            3,
            9000,
            25,
            "ep_pp_t_" + secrets.token_urlsafe(16),
            1,
            4,
            None,
            10,
        ),
    )
