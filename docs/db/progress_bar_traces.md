# progress bar traces

a single retained trace for a progress bar, i.e., the actual amount of time taken for a particular run.

## columns

- `id (integer primary key)`: the internal row identifier
- `progress_bar_id (integer not null references progress_bars(id) on delete cascade)`: the id of the progress bar
- `uid (text unique not null)`: the primary external identifier for the row
- `created_at (real not null)`: when this record was created in seconds since
  the unix epoch

## schema

```sql
CREATE TABLE progress_bar_traces(
    id INTEGER PRIMARY KEY,
    progress_bar_id INTEGER NOT NULL REFERENCES progress_bars(id) ON DELETE CASCADE,
    uid TEXT UNIQUE NOT NULL,
    created_at REAL NOT NULL
);
/* foreign key, search */
CREATE INDEX progress_bar_traces_progress_bar_id_created_at ON progress_bar_traces(progress_bar_id, created_at);
```
