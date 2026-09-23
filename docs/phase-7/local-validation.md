# Phase 7 Local Validation

Use this as a local cross-check of the hosted CI validation.

The script does not install dependencies, change repository source files, or run destructive database migration round-trips.

## Windows PowerShell

From the repository root:

    powershell -ExecutionPolicy Bypass -File .\\scripts\\validate_phase7.ps1

The script requires:

- a working Python environment for `services/api`;
- preferably `services/api/.venv/Scripts/python.exe`, otherwise `python` on PATH;
- Flutter on PATH.

It executes, in order:

1. focused backend stable-ID replay tests;
2. complete backend pytest suite;
3. `flutter --version`;
4. `flutter pub get`;
5. `flutter analyze`;
6. `flutter test`.

Logs are written to:

    tmp/phase7-validation/<timestamp>/

That path is already ignored by the repository.

## Decision rule

Do not mark PR #37 validated unless every command completes with exit code 0.

If any command fails:

- keep the PR draft;
- preserve the log;
- fix the first real failure;
- rerun the entire validation script from the beginning.

A local pass is supporting evidence; PR #37 still requires the hosted GitHub Actions validation to pass.

## What this script deliberately does not do

- no `pip install`;
- no Flutter installation;
- no production database access;
- no Alembic downgrade/reset;
- no merge;
- no automatic PR status change.

PR #35 has a separate migration/finalization gate and must be validated independently.
