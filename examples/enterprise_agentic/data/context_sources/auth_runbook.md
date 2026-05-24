# Auth Rollout Mitigation Runbook

Use this runbook when password reset, credential rotation, or operator login
fails after an auth rollout.

Immediate checks:

1. Compare reset-token verifier errors before and after rollout.
2. Check regional rollout flags for the impacted region.
3. If privileged users are blocked, disable the rollout flag for the impacted
   region before global rollback.
4. Verify reset-token expiry math and cache invalidation.
5. Run synthetic password-reset tests for a privileged test account.

Rollback criteria:

- more than 10 enterprise users blocked
- credential rotation is blocked
- no safe hotfix is available inside 60 minutes

Post-mitigation:

- preserve audit logs in-region
- publish customer-safe update
- open follow-up ticket for permanent fix
