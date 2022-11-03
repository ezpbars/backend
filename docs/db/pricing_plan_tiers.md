# pricing plan tiers

the cost per unit for the tiers of each pricing plan

## columns

-   `id (integer primary key)`: primary database identifier
-   `uid (text unique not null)`: primary stable identifier
-   `pricing_plan_id (integer not null references pricing_plans(id) on delete cascade)`: the pricing plan this tier belongs to
-   `position (integer not null)`: the position of the tier (0, 1, 2, 3, ...). for example,
    position 0 refers to the first X units, where X is the value of the `units` column
-   `units (integer null)`: how many units are in this tier before you get to the next
    tier. null iff there are no higher tiers. positive
-   `unit_price_cents (integer not null)`: price per unit in this tier

## schema

```sql
CREATE TABLE pricing_plan_tiers(
    id INTEGER PRIMARY KEY,
    uid TEXT UNIQUE NOT NULL,
    pricing_plan_id INTEGER NOT NULL REFERENCES pricing_plans(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    units INTEGER NULL,
    unit_price_cents INTEGER NOT NULL
);
/* foreign key, uniqueness */
CREATE UNIQUE INDEX pricing_plan_tiers_pricing_plan_id_position ON pricing_plan_tiers(pricing_plan_id, position);
```
