# user pricing plans

the pricing plans each user has

## columns

- `id (integer primary key)`: primary database identifier
- `uid (text unique not null)`: primary stable identifier
- `user_id (integer unique not null references users(id) on delete cascade)`: the id of the user the pricing plan belongs to
- `pricing_plan_id (integer not null references pricing_plans_id(id) on delete cascade)`: the id of the pricing plan

## schema

```sql
CREATE TABLE user_pricing_plans(
    id INTEGER PRIMARY KEY,
    uid TEXT UNIQUE NOT NULL,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pricing_plan_id INTEGER NOT NULL REFERENCES pricing_plans(id) ON DELETE CASCADE,
);
/* foreign key */
CREATE INDEX user_pricing_plans_pricing_plan_id ON user_pricing_plans(pricing_plan_id);
```
