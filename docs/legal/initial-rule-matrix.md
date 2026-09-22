# Initial Legal Rule Matrix

Status: Phase 0 source-gating document  
Scope: first SIH demo rule pack only

This matrix is intentionally conservative. It identifies candidate checks and authoritative source locations before implementation. It is **not** executable law and must not be treated as a substitute for the current official rules.

## Primary official sources located

1. Department of Consumer Affairs — Legal Metrology (Packaged Commodities) Rules, 2011 resources and amendments  
   https://consumeraffairs.nic.in/taxonomy/term/2645

2. Department of Consumer Affairs — consolidated Packaged Commodities Rules with amendments  
   https://consumeraffairs.nic.in/sites/default/files/file-uploads/latestnews/LM_PCR_All_Amendements.pdf

3. Department of Consumer Affairs — advisory on mandatory declarations on outer retail packages, dated 18 January 2023  
   https://consumeraffairs.nic.in/sites/default/files/file-uploads/latestnews/2023.01.18%20advisory%20for%20outer%20gift%20package%20declarations.pdf

4. Gazette / Department source for the 2 November 2021 amendment affecting Rule 6  
   https://consumeraffairs.nic.in/sites/default/files/file-uploads/latestnews/230946.pdf

5. Department source for the 28 March 2022 amendment, including unit sale price changes  
   https://consumeraffairs.nic.in/sites/default/files/uploads/legal-metrology-acts-rules/GSR226.pdf

## Candidate checks

| Candidate declaration/check | Initial automation target | Current gate |
| --- | --- | --- |
| Manufacturer / packer / importer name and address | Presence + extracted value + evidence region | Needs final applicability review |
| Common/generic name of commodity | Presence + extracted value + evidence region | Needs final applicability review |
| Net quantity | Presence + normalized quantity/unit + evidence region | Needs final applicability review |
| Date declaration | Presence + parsed date text where applicable | Needs commodity/applicability review |
| MRP / retail sale price | Presence + extracted price + evidence region | Needs final wording/applicability review |
| Consumer-care details | Presence + extracted contact text + evidence region | Needs final applicability review |
| Unit sale price | Presence + normalized value where applicable | Needs exception/applicability review |
| Best-before / use-by | Extract if present; compliance check only where legally applicable | Do not encode until applicability is verified |
| Country of origin | Extract if present; required-check only for imported products | Requires imported-product context |
| Physical character/font size | Measurement only with valid calibration evidence | Separate measurement gate |

## Implementation rule

A candidate may move to `verified` only when the implementation note records:

- exact official provision;
- effective date/version;
- applicability;
- exemptions;
- expected evidence;
- deterministic check logic;
- known unsupported cases;
- legal-source reviewer/date.

## Explicit exclusions

- Do not use the February 2025 medical-device draft amendment as operative law unless an enacted Gazette notification is verified.
- Do not infer a violation merely because OCR failed to find text.
- Do not treat food-specific declarations as universally applicable to every packaged commodity.
- Do not encode legal thresholds from screenshots, blogs, generated summaries or memory.

## Phase 0 outcome

The official source family has been identified and the first candidate declaration set has been bounded. Exact executable rule definitions remain a legal-source-gated Phase 4 task.
