# progress bar trace steps

the actual amount of time taken for a particular step within a trace

## columns

- `id (integer primary key)`: the internal row identifier
- `progress_bar_trace_id (integer not null references progress_bar_traces(id) on delete cascade)`:
  the id of the progress bar trace
- `progress_bar_step_id (integer not null references progress_bar_steps(id) on delete cascade)`:
  the id of the particular step within the progress bar which this is providing information about
- `uid (text unique not null)`: the primary external identifier for the row
- `iterations (integer null)`: the number of iterations if the step is iterated, otherwise null
- `started_at (real not null)`: when the step was started in seconds since the unix epoch
- `finished_at (real not null)`: when the step was finished in seconds since the unix epoch

## schema

```sql
CREATE TABLE progress_bar_trace_steps(
    id INTEGER PRIMARY KEY,
    progress_bar_trace_id INTEGER NOT NULL REFERENCES progress_bar_traces(id) ON DELETE CASCADE,
    progress_bar_step_id INTEGER NOT NULL REFERENCES progress_bar_steps(id) ON DELETE CASCADE,
    uid TEXT UNIQUE NOT NULL,
    iterations INTEGER NULL,
    started_at REAL NOT NULL,
    finished_at REAL NOT NULL
);
/* foreign key, uniqueness */
CREATE UNIQUE INDEX progress_bar_trace_steps_progress_bar_trace_id_progress_bar_step_id
    ON progress_bar_trace_steps(progress_bar_trace_id, progress_bar_step_id);
/* foreign key */
CREATE INDEX progress_bar_trace_steps_progress_bar_step_id ON progress_bar_trace_steps(progress_bar_step_id);
```
