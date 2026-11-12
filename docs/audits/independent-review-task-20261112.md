# Independent review task card

Objective: reproduce #103/#104/#105 evidence and repair verified security defects without deployment or access changes. Exact dependency heads: #103 `0c0a99f62f8e25df6c66a74ea8447922f57ea16d`; #104 `f41e8c7ee43575d50771ddc4cfe96389c468243e`; #105/base `58cdc4df30004df424b2ad9da7f5905321fadf63`. Main: `b973e4330888970184cf9f90fb9487a1ff563b3b`.

Branch: `research/independent-staging-review-20261112`. Owned files: checkpoint adapter and paper-session/BFF integration, fixed-origin public transport and two historical adapters, their tests, acceptance workflow and independent evidence reports. Existing accounting/risk engines and hosted website remain intact.

Expected behavior: reject unanchored or rolled-back owner journals, require a separately authenticated append-only checkpoint authority before constructing the browser BFF, halt on authority failure, reject redirected/unbounded public-data responses. An uncertain cross-database commit must halt, never silently adopt an unanchored extension.

Tests: independently run all three pinned unit suites, current CI/log inspection, negative redirect and journal-truncation reproductions, real disposable PostgreSQL isolation/revocation/quota/checkpoint tests, paper crash/idempotency assertions, website logic, dependency audit, Bandit, Ruff, secret and workflow checks. Budget: bounded public GETs and local temporary resources; no paid infrastructure, production data or authentication credentials. Real Auth0/proxy/native Android require unavailable independent acceptance evidence.

Rollback: close the unmerged draft; no deployment or existing system mutation occurs. Stop conditions: owner-only credentials/configuration/infrastructure changes, public access, live trading, reserved 2027 data or an unresolved critical acceptance failure. No branch deletion, merge or protected-history rewrite.
