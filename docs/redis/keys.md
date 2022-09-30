# redis keys

the keys that we use in redis

## standard keys

- `jobs:hot` used for the hot queue for jobs in jobs.py
- `cognito:jwks` used for caching our cognito keys in auth.py
- `trace:{user_sub}:{progress_bar_name}:{trace_uid}` goes to a hash with the following keys:
  - `created_at`: seconds since the unix epoch when the trace was created
  - `last_updated_at`: when we last saw a change to this trace in seconds since the unix epoch
  - `current_step`: the last started step position
  - `done`: true if completed, false if not
- `trace:{user_sub}:{progress_bar_name}:{trace_uid}:step:{step_position}`: goes to a hash with the following keys:
  - `step_name`: the name for the step
  - `iteration`: either 0 if one-off, or a number for the last iteration that's already been completed
  - `iterations`: either 0 if one-off, or the total number of iterations
  - `started_at`: when the step was started in seconds since the unix epoch
  - `finished_at`: when the step completed in seconds since the unix epoch
- `stats:{user_sub}:{progress_bar_name}:{version}:{step_position}:{technique}`: where technique for percentile options is formatted via `percentile_{percentile}` goes to a hash with the following keys:
  - `a`: the first variable in the fit; for all techniques except best_fit.linear this is the only variable required - for example, if the technique is arithmetic mean, this is the arithmetic mean. for best_fit.linear, this is the slope of the fit
  - `b`: the second variable of the fit; unused except for best_fit.linear, where this is the intercept of the fit


## pubsub keys

- `ps:trace:{user_sub}:{progress_bar_name}:{trace_uid}`: gets sent one message with arbitrary content whenever the corresponding trace is updated (or created) in redis
