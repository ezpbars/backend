# progress bar steps

describes a particular step within a progress bar

## columns

- `id (integer primary key)`: the internal row identifier
- `progress_bar_id (integer not null references progress_bars(id) on delete cascade)`: the id of the progress bar
- `uid (text unique not null)`: the primary external identifier for the row
- `name (text not null)`: the unique identifier for the user when referencing
  the step when combined with the progress bar if it has the special value
  `default`, this is not an actual step, but rather the configuration to use
  for new steps within this progress bar, consequently, no step can be named default.
- `position (integer not null)`: when the step occurs within the overall task,
  i.e., 1 is the first step. The default step has a position of 0
- `iterated (integer not null)`: 1 if the step is iterated, i.e., it consists of
  many, identical, smaller steps, 0 for a one-off step, i.e., a step which is
  not repeated. Ignored for the default step
- `one_off_technique (text not null)`: required for non-iterated i.e., one-off
  steps. The technique to use to predict the time step will take. one of the
  following values:
  - `percentile`: the fastest amount of time slower than a fixed percentage of
    the samples, see also: one_off_percentile
  - `harmonic_mean`: the harmonic mean of the samples, https://en.wikipedia.org/wiki/Harmonic_mean
  - `geometric_mean`: the geometric mean of the samples, https://en.wikipedia.org/wiki/Geometric_mean
  - `arithmetic_mean`: the arithmetic mean of the samples, https://en.wikipedia.org/wiki/Arithmetic_mean
- `one_off_percentile (real not null)`: required for non-iterated steps using the
  percentile technique. the percent of samples which should complete faster than
  the predicted amount of time. for example, `25` means a quarter of samples
  complete before the progress bar reaches the end. Typically, a high value,
  such as 90, is chosen, since it's better to surprise the user with a faster
  result, than to annoy them with a slower result.
- `iterated_technique (text not null)`: required for iterated steps. The technique
  used to predict the time the step takes, unless otherwise noted, the technique
  is applied to the normalized speed, i.e., the speed divided by the number of
  iterations and the prediction is the predicted normalized speed multiplied by
  the number of iterations. Must be one of the following values:
  - `best_fit.linear`: fits the samples to t = mn+b where t is the predicted
    time, m is a variable, n is the number of iterations, and b is also a
    variable. This fit does not merely work on normalized speed.
  - `percentile`: see one_off_technique
  - `harmonic_mean`: see one_off_technique
  - `geometric_mean`: see one_off_technique
  - `arithmetic_mean`: see one_off_technique
- `iterated_percentile (real not null)`: see one-off percentile
- `created_at (real not null)`: when this record was created in seconds since
  the unix epoch

## schema

```sql
CREATE TABLE progress_bar_steps(
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
);
/* foreign key, uniqueness */
CREATE UNIQUE INDEX progress_bar_steps_progress_bar_id_name ON progress_bar_steps(progress_bar_id, name);
/* uniqueness, search */
CREATE UNIQUE INDEX progress_bar_steps_progress_bar_id_position ON progress_bar_steps(progress_bar_id, position);
```
