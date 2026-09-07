# vertical/ — tender/bid-response skin

Domain-specific code and data only. Nothing here should be needed by a
different vertical (KYC intake, grant applications, RFP-response) — if it
is, it belongs in `harness/` instead.

Planned components:

- `ingestion/` — parsers for tender document formats (PDF requirement docs,
  ITT/RFQ packs, past-bid case study library)
- `evals/` — domain-specific golden sets and rubrics (tender requirement →
  correct response pairs)
- `ui/` — workflow interface a non-technical user can operate and trust

Nothing here yet. First real content arrives with M1: synthetic/public
tender docs to build the parse → retrieve → draft → self-check flow against.
