# user usages

stores the coarse usage information for each user and approximate time information.

## columns

- `id (integer primary key)`: primary database identifier
- `uid (text unique not null)`: primary stable identifier
- `user_id (integer not null references users(id) on delete cascade)`: the id of the user the usage belongs to
- `traces (integer not null)`: the number of traces the user has used
- `period_started_at (real not null)`: the approximate time of the first trace in the period
- `period_ended_at (real not null)`: the approximate time of the last trace in the period
- `stripe_invoice_id (integer not null references stripe_invoices(id) on delete set null)`: the id of the invoice in the stripe_invoices table
- KEY: user_id
- KEY: period_started_at

## schema

```sql
CREATE TABLE user_usages(
    id INTEGER PRIMARY KEY,
    uid TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    traces INTEGER NOT NULL,
    period_started_at REAL NOT NULL,
    period_ended_at REAL NOT NULL,
    stripe_invoice_id TEXT NULL
);
/* foreign key */
CREATE INDEX user_usages_user_id ON user_usages(user_id);
/* foreign key */
CREATE INDEX user_usages_period_started_at ON user_usages(period_started_at);
```
