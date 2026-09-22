# Phase 0 — Foundation Freeze and Repository Setup

## Purpose

Phase 0 converts the approved blueprint into a buildable repository without starting product feature development too early.

## Scope

This phase establishes:

- repository structure and engineering conventions;
- source-of-truth scope boundaries;
- stack decision record;
- legal-source verification gate;
- configuration/secrets handling;
- initial CI/repository checks;
- ownership of open blueprint decisions.

## Open decisions that must be frozen before Phase 1

1. Initial commodity/package categories used for the SIH demo.
2. First set of Legal Metrology checks to implement.
3. Calibration-card/reference approach for physical font-size checks.
4. Initial split between on-device and server-side processing.
5. Supervisor permissions in the prototype.
6. Whether any editable report export is required beyond PDF.
7. Initial hosting/deployment target.

These items were intentionally left open in Foundation Blueprint v1.0. They must not be silently guessed in code.

## Phase 0 exit gate

Phase 0 is complete when:

- the core scope is unchanged and documented;
- optional ideas remain outside the build;
- the seven open decisions above have owners and decisions, or are explicitly deferred without blocking Phase 1;
- the repository layout and contribution rules are established;
- official-source verification is mandatory before legal rules are encoded;
- a basic repository CI check passes;
- no production feature has been represented as complete.

## Next phase

Phase 1 starts the data foundation: project runtime setup, persistence models, local inspection draft flow, and the authentication skeleton defined by the roadmap.
