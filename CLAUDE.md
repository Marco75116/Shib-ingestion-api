# Project guidelines

- Design for production scale: assume billions of transfers and millions of wallets. Never write a query or
  endpoint that scans the full `transfers` table; always bound by a time window or primary-key range, read
  from pre-aggregated tables, and cap result sizes.
