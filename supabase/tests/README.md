# Database tests

`visibility_test.sql` checks the row-level security in `../migrations/0003_platform.sql`: who sees which changes, documents, contracts and schedule of values; that a proposal can't be sent before the checks run and every finding is explained; that events can't be edited; that you can only act for your own company; and that a field link can add a submission but read nothing.

It runs on a plain local Postgres 16 with a small stand-in for Supabase's `auth` and `storage` schemas:

```
bash tools/db_test.sh
```

The script starts a throwaway database, loads `stub.sql`, applies the migration, and runs the test. Every check prints `ok: ...`; the last line is `ALL VISIBILITY TESTS PASSED`.
