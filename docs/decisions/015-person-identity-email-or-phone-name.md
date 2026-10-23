# 015: Person identity = same email, or same phone + same name

- **Status:** accepted
- **Date:** 2026-10-22

## Context
A person can send several resume files (format duplicates, updated versions). They should be one candidate with versions, and only the current version should be searchable. The first rule was "same email OR same phone". The end-to-end eval found **436 people in the app vs 563 true people**: over-merging. The synthetic `555-01xx` numbers collide, and real resumes also share office lines.

## Decision
In `store._store_processed`, inside the store transaction:
- If the profile has an email: same normalized email (lowercased) = same person.
- Only if there is **no** email: same normalized phone (last 10 digits) **and** same name (case-insensitive).
- A phone alone never merges people; a matching phone with a different email is a different person.
- New people with an email are inserted with `ON CONFLICT (email_norm) DO UPDATE`, so two versions of one person processed at the same moment become one person (this race violated `people_email_uq` during testing).
- The newly stored file becomes `is_current`; the previous one is unset.

## Alternatives considered
- **Email OR phone:** caused the over-merge.
- **Fuzzy name + employer matching:** better recall without email, but risky to merge two different people silently; needs a review UI.
- **Never merge, show all files as separate candidates:** duplicates in search and shortlists.

## Tradeoffs and consequences
- **Gain:** after re-ingesting from scratch, 563 = 563 people and 26/26 multi-file people linked. Integration tests cover each rule and the concurrent upsert.
- **Give up:** without an email, a slightly different spelling of the name creates a second person. The last processed version becomes current, even if it's older.
- **Revisit if:** real data has many resumes without email, or recruiters need a manual "merge / split person" action.
