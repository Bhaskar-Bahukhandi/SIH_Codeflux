# Legal Rule Source Gate

The rule engine is deterministic and versioned, but its legal content must not be invented from memory or generated summaries.

## Before implementing any rule

Record:

1. official source title;
2. issuing authority;
3. rule / provision identifier;
4. official source URL or Gazette reference;
5. effective date;
6. applicability conditions;
7. exemptions / exceptions;
8. exact system check being implemented;
9. expected evidence required from the package;
10. review date and reviewer.

## Allowed implementation status

- **verified** — checked against an official source and ready for test encoding;
- **needs-review** — source located but applicability/wording still being checked;
- **not-implemented** — intentionally unsupported;
- **superseded** — retained only for historical/versioned inspections where required.

## Safety rule

When applicability, evidence quality, or current legal status is uncertain, the system must not manufacture a confident compliance verdict. It should return a review/recheck/not-evaluated state.
