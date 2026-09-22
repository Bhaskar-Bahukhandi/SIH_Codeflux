# Phase 1 Authentication Foundation

## Purpose

The SIH prototype now has a real authentication boundary rather than a UI-only login screen.

## Prototype authentication model

- Users are provisioned administratively.
- Passwords are stored only as Argon2 hashes.
- Login returns a signed, time-limited JWT access token.
- Protected API calls use `Authorization: Bearer <token>`.
- The current user and role are reloaded from the database on each authenticated request.
- Inactive users are rejected.
- There is no public self-registration endpoint.

## Roles in this slice

### Officer

- create inspections;
- list/view only their own inspections;
- edit their own draft inspections;
- submit their own draft inspections for review.

### Supervisor

- list/view inspections for review/monitoring;
- cannot create or edit officer inspections in this phase.

### Admin

- may read inspection data through the same protected API;
- user-management endpoints are intentionally not exposed yet.

## User bootstrap

After applying migrations, create a prototype account from `services/api`:

```bash
python -m app.cli.create_user \
  --email officer@example.test \
  --name "Demo Officer" \
  --role officer
```

The command prompts for the password without requiring it as a command-line argument.

## Security limitations

This is a suitable foundation for the SIH prototype, not a complete identity platform.

Not yet implemented:

- password reset;
- refresh-token rotation;
- MFA;
- SSO/OIDC;
- organization tenancy;
- login throttling / lockout;
- security-event dashboard.

Those should be added only if the deployment context requires them.

## Deployment gate

The development JWT secret is intentionally recognizable. Any non-development/test environment must use a different secret of at least 32 characters or application configuration validation fails.
