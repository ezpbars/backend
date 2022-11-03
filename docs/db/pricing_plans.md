# pricing plans

stores the pricing plans that we offer

## columns

-   `id (integer primary key)`: primary database identifier
-   `uid (text unique not null)`: primary stable identifier
-   `slug (text unique not null)`: an internal identifer for the plan, e.g., 'public',
-   `stripe_price_id (text unique not null)`: the id of the price on stripe
-   `unit_amount (integer not null)`: indicates number of traces per unit

## schema

```sql
CREATE TABLE pricing_plans(
    id INTEGER PRIMARY KEY,
    uid TEXT UNIQUE NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    stripe_price_id TEXT UNIQUE NOT NULL,
    unit_amount INTEGER NOT NULL
);
```
