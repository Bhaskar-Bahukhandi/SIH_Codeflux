# Initial Legal Rule Matrix

Status: active source-gating document  
Scope: SIH prototype rule packs

This matrix identifies candidate checks and their implementation gate. It is **not** executable law and must not be treated as a substitute for the current official rules.

## Primary official sources

1. Department of Consumer Affairs — Legal Metrology (Packaged Commodities) Rules, 2011 resources and amendments  
   https://consumeraffairs.nic.in/taxonomy/term/2645

2. Department of Consumer Affairs — consolidated Packaged Commodities Rules with amendments  
   https://consumeraffairs.nic.in/sites/default/files/file-uploads/latestnews/LM_PCR_All_Amendements.pdf

3. Department of Consumer Affairs — advisory on mandatory declarations on outer retail packages, dated 18 January 2023  
   https://consumeraffairs.nic.in/sites/default/files/file-uploads/latestnews/2023.01.18%20advisory%20for%20outer%20gift%20package%20declarations.pdf

4. G.S.R. 779(E), 2 November 2021 — amendment affecting Rule 6  
   https://consumeraffairs.nic.in/sites/default/files/file-uploads/latestnews/230946.pdf

5. G.S.R. 226(E), 28 March 2022 — later commencement / unit-sale-price amendment  
   https://consumeraffairs.nic.in/sites/default/files/uploads/legal-metrology-acts-rules/GSR226.pdf

6. G.S.R. 722(E), 6 October 2023 — later packaged-commodities amendment  
   https://consumeraffairs.nic.in/sites/default/files/uploads/legal-metrology-acts-rules/2023.10.6%20amendment%20in%20PCR.pdf

## Candidate checks

| Candidate declaration/check | Initial automation target | Current gate |
| --- | --- | --- |
| Manufacturer / packer / importer name and address | Presence + extracted value + evidence region | Needs extraction + applicability review |
| Common/generic name of commodity | Presence + extracted value + evidence region | Needs extraction + applicability review |
| **Net quantity — Rule 6(1)(c)** | Preliminary declaration-evidence presence | **Verified for lmpc-retail-evidence@2026.09-v1 narrow supported profile** |
| Date declaration | Presence + parsed date text where applicable | Needs commodity/applicability review |
| **MRP / retail sale price — Rule 6(1)(e)** | Preliminary declaration-evidence presence | **Verified for lmpc-retail-evidence@2026.09-v1 narrow supported profile** |
| Consumer-care details | Presence + extracted contact text + evidence region | Needs extraction + applicability review |
| Unit sale price | Presence + normalized value where applicable | Needs exception/applicability review |
| Best-before / use-by | Extract if present; compliance check only where legally applicable | Do not encode until applicability is verified |
| Country of origin | Extract if present; required-check only for imported products | Requires imported-product context |
| Physical character/font size | Measurement only with valid calibration evidence | Separate measurement gate |

## First verified pack

See:

- packages/rulepacks/lmpc-retail-evidence-v1.json
- docs/legal/verified-rule-pack-v1.md

The first pack supports only packages for which the officer confirms:

- intended for retail sale;
- not meant for an industrial/institutional consumer;
- does not exceed 25 kg / 25 L.

Outside that profile the engine returns not_evaluated rather than pretending to cover every legal exception.

## Implementation rule

A candidate may move to verified only when the implementation note records:

- exact official provision;
- source/Gazette reference;
- effective/current wording note;
- applicability conditions;
- exemptions / unsupported scope;
- exact system check being implemented;
- expected evidence;
- legal-source review date.

## Explicit exclusions

- Do not use a draft/proposed amendment as operative law.
- Do not infer a violation merely because OCR/extraction failed to find text.
- Do not treat food-specific declarations as universally applicable to every packaged commodity.
- Do not encode legal thresholds from screenshots, blogs, generated summaries or memory.
- Do not expand a rule pack silently; publish a new version and preserve the old pack hash for reproducibility.
