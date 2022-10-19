from itgs import Itgs


async def up(itgs: Itgs) -> None:
    conn = await itgs.conn()
    cursor = conn.cursor("strong")
    await cursor.execute(
        """CREATE TABLE progress_bars(
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        uid TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        sampling_max_count INTEGER NOT NULL,
        sampling_max_age_seconds INTEGER NULL,
        sampling_technique TEXT NOT NULL,
        version INTEGER NOT NULL,
        created_at REAL NOT NULL
        );""",
    )
    await cursor.execute(
        """CREATE UNIQUE INDEX progress_bars_user_id_name ON progress_bars(user_id, name);"""
    )
    await cursor.execute(
        """CREATE TABLE progress_bar_traces(
            id INTEGER PRIMARY KEY,
            progress_bar_id INTEGER NOT NULL REFERENCES progress_bars(id) ON DELETE CASCADE,
            uid TEXT UNIQUE NOT NULL,
            created_at REAL NOT NULL
        );"""
    )
    await cursor.execute(
        """CREATE INDEX progress_bar_traces_progress_bar_id_created_at ON
        progress_bar_traces(progress_bar_id, created_at);"""
    )
    await cursor.execute(
        """CREATE TABLE progress_bar_steps(
            id INTEGER PRIMARY KEY,
            progress_bar_id INTEGER NOT NULL REFERENCES progress_bars(id) ON DELETE CASCADE,
            uid TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            position INTEGER NOT NULL,
            iterated INTEGER NOT NULL,
            one_off_technique TEXT NOT NULL,
            one_off_percentile REAL NOT NULL,   
            iterated_technique TEXT NOT NULL,
            iterated_percentile REAL NOT NULL,
            created_at REAL NOT NULL
        );"""
    )
    await cursor.execute(
        """CREATE UNIQUE INDEX progress_bar_steps_progress_bar_id_name ON
        progress_bar_steps(progress_bar_id, name);"""
    )
    await cursor.execute(
        """CREATE UNIQUE INDEX progress_bar_steps_progress_bar_id_position ON
        progress_bar_steps(progress_bar_id, position);"""
    )
    await cursor.execute(
        """CREATE TABLE progress_bar_trace_steps(
            id INTEGER PRIMARY KEY,
            progress_bar_trace_id INTEGER NOT NULL REFERENCES progress_bar_traces(id) ON DELETE CASCADE,
            progress_bar_step_id INTEGER NOT NULL REFERENCES progress_bar_steps(id) ON DELETE CASCADE,
            uid TEXT UNIQUE NOT NULL,
            iterations INTEGER NULL,
            started_at REAL NOT NULL,
            finished_at REAL NOT NULL
        );"""
    )
    await cursor.execute(
        """CREATE UNIQUE INDEX progress_bar_trace_steps_progress_bar_trace_id_progress_bar_step_id
            ON progress_bar_trace_steps(progress_bar_trace_id, progress_bar_step_id);"""
    )
    await cursor.execute(
        """CREATE INDEX progress_bar_trace_steps_progress_bar_step_id ON
        progress_bar_trace_steps(progress_bar_step_id);"""
    )
