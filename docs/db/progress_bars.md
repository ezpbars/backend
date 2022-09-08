# progress bars

describes a task: a sequence of steps where each step takes a constant amount of
time. for example, the 'make a pizza' task would consist of 'make pizza dough',
'add sauce', and 'bake' where it's a reasonable assumption that the amount of
time for each step comes from a consistent distribution.

## columns

- `id (integer primary key)`: the internal row identifier
- `user_id (integer not null references users(id) on delete cascade)`: the id of
  the user the progress bar is owned by
- `uid (text unique not null)`: the primary external identifier for the row
- `name (text not null)`: the unique identifier for the user when referencing the progress bar
- `sampling_max_count (integer not null)`: the maximum number of samples to retain for prediction
- `sampling_max_age_seconds (integer null)`: the maximum age of samples to
  retain; a value of null means no age limit is applied
- `sampling_technique (text not null)`: one of `systematic`, or `simple_random` where:
  - `systematic`: selects and retains each trace unless a trace has already been
    retained within a minimum interval the intervals chosen such that the
    maximum number of samples taken over the maximum age (one week if not set)
    does not exceed the max count for this progress bar; for example, if the max
    count is ten, and the interval is five seconds, then this will retain at most
    one sample every two seconds. Tends to over sample low periods of activity,
    but has a hard limit on the number of traces retained.
  - `simple_random`: selects and retains each trace with equal probability. The
    probability is initialized to one and tends towards x/n where x is the max
    count and n is the number of traces over the previous rolling max age (one
    week if not set). Accurately samples but has no hard limit on the number of
    samples retained.
- `version (integer not null)`: the numebr of times the steps and traces had to
  be reset because we received a trace with different steps
- `created_at (real not null)`: when this record was created in seconds since
  the unix epoch

## schema

```sql
CREATE TABLE progress_bars(
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    uid TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    sampling_max_count INTEGER NOT NULL,
    sampling_max_age_seconds INTEGER NULL,
    sampling_technique TEXT NOT NULL,
    created_at REAL NOT NULL
);
/* foreign key, uniqueness */
CREATE UNIQUE INDEX progress_bars_user_id_name ON progress_bars(user_id, name);
```
