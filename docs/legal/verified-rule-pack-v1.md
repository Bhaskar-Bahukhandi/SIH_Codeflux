# Verified Legal Basis — LMPC Retail Evidence Rule Pack v1

Status: verified for the **narrow supported prototype scope**  
Rule pack: `lmpc-retail-evidence@2026.09-v1`  
Source review date: 23 September 2026

## Why this document exists

Phase 5 must not turn OCR/extraction output into legal conclusions unless the exact rule source, applicability boundary and automated check are documented.

This verification covers only two preliminary declaration-evidence checks:

1. Rule 6(1)(c) — net quantity;
2. Rule 6(1)(e) — retail sale price / MRP.

It does not verify every Legal Metrology declaration and does not replace legal review.

## Official sources checked

### Department consolidated rules

Department of Consumer Affairs, *The Legal Metrology (Packaged Commodities) Rules, 2011 with amendments*:

https://consumeraffairs.nic.in/sites/default/files/file-uploads/latestnews/LM_PCR_All_Amendements.pdf

The consolidated text identifies Rule 3 applicability exclusions and Rule 6 package declarations. Rule 6(1)(c) covers net quantity in a standard unit of weight/measure or number where applicable. Rule 6(1)(e) covers retail sale price / maximum retail price.

### G.S.R. 779(E), 2 November 2021

Official amendment:

https://consumeraffairs.nic.in/sites/default/files/file-uploads/latestnews/230946.pdf

Among other changes, this amendment modified Rule 6(1)(e) so the retail sale price wording uses Indian currency. Its commencement was subsequently deferred.

### G.S.R. 226(E), 28 March 2022

Official amendment:

https://consumeraffairs.nic.in/sites/default/files/uploads/legal-metrology-acts-rules/GSR226.pdf

This moved the relevant 2021-amendment commencement to 1 October 2022 and also dealt with unit-sale-price provisions.

### Department advisory dated 18 January 2023

Official advisory:

https://consumeraffairs.nic.in/sites/default/files/file-uploads/latestnews/2023.01.18%20advisory%20for%20outer%20gift%20package%20declarations.pdf

The advisory lists net quantity and retail sale price / MRP among mandatory information for packages meant for retail sale.

### G.S.R. 722(E), 6 October 2023

Official amendment:

https://consumeraffairs.nic.in/sites/default/files/uploads/legal-metrology-acts-rules/2023.10.6%20amendment%20in%20PCR.pdf

This made later changes including package definitions, date-declaration provisions, unit-sale-price exceptions and rule 26 changes. The first rule pack does not encode those additional areas.

## Scope supported by rule pack v1

The first rule pack runs only when the officer supplies all three factual context values and they match this profile:

- intended for retail sale = yes;
- industrial/institutional consumer = no;
- package exceeds 25 kg / 25 L = no.

This intentionally avoids claiming support for every edge case or exemption.

If context is incomplete, the engine returns `indeterminate`.

If the package is outside this narrow profile, the engine returns `not_evaluated`, not a legal conclusion about whether the law does or does not apply.

## Rule 6(1)(c) — net quantity

### Verified legal basis

For the supported retail profile, Rule 6(1)(c) requires a net-quantity declaration in the applicable standard unit / number form.

### Current automated check

The engine checks the latest current Phase 4 declaration summary for `net_quantity`.

It does **not** yet verify:

- physical quantity accuracy;
- permissible error;
- unit typography;
- physical font size;
- all Rule 11/13 presentation requirements.

### Result mapping

- `single_source` or `consistent` -> `pass` for declaration-evidence presence;
- `conflict` -> `manual_verification_required`;
- `not_detected` -> `manual_verification_required`.

A technical `not_detected` result is not treated as proof that the declaration is absent.

## Rule 6(1)(e) — retail sale price / MRP

### Verified legal basis

For the supported retail profile, Rule 6(1)(e) requires the retail sale price / maximum retail price declaration. The current wording reflected by the official consolidated text and 2021 amendment requires the maximum retail price inclusive of taxes in Indian currency.

### Current automated check

The engine checks the latest current Phase 4 declaration summary for `mrp`.

It does **not** yet verify every formatting requirement, tax wording, price rounding issue, special commodity proviso, or physical presentation requirement.

### Result mapping

- `single_source` or `consistent` -> `pass` for declaration-evidence presence;
- `conflict` -> `manual_verification_required`;
- `not_detected` -> `manual_verification_required`.

## Draft/proposed material explicitly excluded

A Department release dated 14 July 2024 **proposed** changing the quantity-based applicability boundary for retail packages and invited stakeholder comments. It is not treated as an enacted rule by this pack.

A February 2025 medical-device item on the Department website is explicitly a **Draft Legal Metrology (Packaged Commodities) Amendment Rules, 2025** consultation and is not treated as operative law by this pack.

The official Department packaged-commodities materials searched on 23 September 2026 did not surface a later enacted amendment changing these two rule-pack checks. This must be re-verified before publishing a future rule-pack version.

## Decision rule

This pack supports preliminary evidence review only.

It does not:

- issue a final legal verdict;
- infer non-compliance from OCR failure;
- determine physical absence without human verification;
- calculate penalties;
- issue notices;
- measure legal font size.

Those remain later, separately gated capabilities.
