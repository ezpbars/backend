# stripe invoices

information of invoices from stripe for each user

## columns

- `id (integer primary key)`: primary database identifier
- `uid (text unique not null)`: primary stable identifier
- `stripe_id (text unique not null)`: the id of the invoice on stripe
- `hosted_invoice_url (text not null)`: The URL for the hosted invoice page, which allows customers to view and pay an invoice. If the invoice has not been finalized yet, this will be null.
- `total (integer not null)`: The total amount in cents that will be/was charged, including tax and discounts.
- `created_at (real not null)`: The time at which the invoice was created. Measured in seconds since the Unix epoch.

## schema

```sql
CREATE TABLE stripe_invoices(
    id INTEGER PRIMARY KEY,
    uid TEXT UNIQUE NOT NULL,
    stripe_id TEXT UNIQUE NOT NULL,
    hosted_invoice_url TEXT NOT NULL,
    total INTEGER NOT NULL,
    created_at REAL NOT NULL
);
```
