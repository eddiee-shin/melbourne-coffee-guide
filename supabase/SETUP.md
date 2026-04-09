# Melbourne Coffee Guide Supabase setup

This repo now includes the database-side migration artifacts for Supabase.

Files
- `supabase/schema.sql` — tables, indexes, views, RLS starter policies
- `scripts/import_cafes.mjs` — import / export tool for cafe seed data

Schema summary
- `cafes` stores canonical cafe content from `data.json` / `data.csv`
- `cafe_likes` stores viewer likes, one per cafe per viewer identity
- `cafe_comments` stores one-line comments with moderation status (`pending`, `approved`, `hidden`)
- `cafes_with_feedback` provides aggregate counts for frontend cards and detail views

Recommended deployment order
1. Run `supabase/schema.sql` in the Supabase SQL editor.
2. Import cafes with the script in dry-run mode first:
   - `node scripts/import_cafes.mjs --mode dry-run`
3. Preview CSV or SQL output if you want file-based import:
   - `node scripts/import_cafes.mjs --mode csv --output /tmp/cafes.csv`
   - `node scripts/import_cafes.mjs --mode sql --output /tmp/cafes_upsert.sql`
4. Or upsert directly into Supabase using REST:
   - `SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... node scripts/import_cafes.mjs --mode rest`

Import notes
- The script derives a stable `slug` from cafe name and uses it as the upsert key.
- It maps `oneLiner` from JSON to `one_liner` in the database.
- It is dry-run friendly and prints a summary without touching Supabase unless you choose `--mode rest`.

RLS notes
- `cafes` is readable by the public.
- Likes can be inserted publicly if you keep the starter policy.
- Comments can be inserted publicly as `pending` and read publicly only when `approved`.
- For stricter moderation, keep raw feedback reads/writes restricted and use the service role for admin actions.
