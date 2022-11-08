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
- `stats:{user_sub}:{progress_bar_name}:{version}:{technique}`: where technique for percentile options is formatted via `percentile_{percentile}` goes to a number which corresponds to the estimated overall time for a new trace. the technique here is referring to the one-off technique of the default step. the value is the estimated time of a newly started trace in seconds
- `stats:{user_sub}:{progress_bar_name}:{version}:{step_position}:{technique}`: where technique for percentile options is formatted via `percentile_{percentile}` goes to a hash with the following keys:
  - `a`: the first variable in the fit; for all techniques except best_fit.linear this is the only variable required - for example, if the technique is arithmetic mean, this is the arithmetic mean. for best_fit.linear, this is the slope of the fit
  - `b`: the second variable of the fit; unused except for best_fit.linear, where this is the intercept of the fit
- `tcount:{user_sub}:{progress_bar_name}:{version}`: a sorted set where the values are arbitrary and the scores are the timestamps in seconds since the unix epoch of when the trace occurred. Can be used to calulate the number of traces in a given time period. Clipped to the sampling max age in seconds.
- `tcount:{utc_year}:{utc_month}`: goes to a hash where the keys are user subs and the values are the number of traces created by the user in the specified month based on the stored trace created at 
- `example:{uid}`: stores the result of the example job with the given uid

## pubsub keys

- `ps:trace:{user_sub}:{progress_bar_name}:{trace_uid}`: gets sent one message with arbitrary content whenever the corresponding trace is updated (or created) in redis
- `ps:job:{job_uid}`: used, if supported, when a job is able to report when it's completed
- `updates:{repo}`: used to indicate that the main branch of the given repository was updated
