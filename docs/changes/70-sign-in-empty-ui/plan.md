# Plan: Sign-in and empty UI (skeleton 2/3)

| | |
|---|---|
| **Issue** | #70 |
| **Spec** | [spec.md](spec.md) (Accepted); [ADR-0013](../../adr/0013-origin-check.md) (Accepted) |
| **Status** | Approved |
| **Date** | 2026-11-27 |

## Context

Slice 2 of the walking skeleton (#22). `jobfinder-web` is deployed behind IAP with only `/health`. This slice adds the app-side IAP JWT and owner check, the `Origin == "https://" + Host` check (ADR-0013), `settings/owner` on first sign-in, and empty pages for 360 px and desktop (spec R1–R10, AC1–AC18).

Reused as they are: `Settings`/`get_settings` in `apps/jobfinder/src/jobfinder/config.py`; `app` and `/health` in `src/jobfinder/web/app.py`; the `owner-email` secret that `web` already reads (`infra/platform/secrets.tf`); `datastore.user` for `web` (`runtime_firestore`, `infra/platform/iam.tf`); the `project_number` variable of `infra/app`. No platform change is needed.

Right after approval, the first commit saves this plan as `docs/changes/70-sign-in-empty-ui/plan.md`; code comes after.

## Files that change

| File | Change |
|---|---|
| `docs/changes/70-sign-in-empty-ui/plan.md` | new, this plan (first commit) |
| `apps/jobfinder/pyproject.toml`, `uv.lock` | `uv add pyjwt[crypto] google-cloud-firestore`; `httpx` moves from the dev group to runtime (JWK fetch) |
| `src/jobfinder/config.py` | `environment` default `production`; add `owner_email`, `project_number`; `K_SERVICE` read at startup; no origins setting |
| `src/jobfinder/web/auth.py` | new: JWK source + TTL cache, `verify_iap_jwt`, `require_owner`, `dev` stand-in identity |
| `src/jobfinder/web/csrf.py` | new: `check_origin` dependency |
| `src/jobfinder/storage/settings_repo.py` | new: `SettingsRepository` protocol, in-memory fake, Firestore impl (client imported lazily), `ensure_owner` |
| `src/jobfinder/web/app.py` | `create_app()` factory with the `dev` + `K_SERVICE` guard; module-level `app`; `/health` outside the protected router; protected router for `/`, `/profiles`, `/settings`, `/runs`; generic 401/403 handlers |
| `src/jobfinder/web/templates/{base,profiles,settings,runs,error}.html`, `static/app.css` | new: shell, empty states, generic error page |
| `infra/app/cloud_run_web.tf` | `env`: `JOBFINDER_ENVIRONMENT=production`, `JOBFINDER_PROJECT_NUMBER`, `JOBFINDER_OWNER_EMAIL` from secret `owner-email`, version `latest` |
| `docs/requirements/use-cases.md` | UC-01 wording only if it diverges (Sign out, placeholder pages) |
| `tests/conftest.py`, `tests/unit/{test_config,test_auth,test_csrf,test_pages,test_settings_repo,test_routes}.py` | new; `tests/unit/test_skeleton.py` adapted to the factory |

ADR-0008 is not edited (ADR-0013 supersedes §5 only).

## Steps

1. Commit `plan.md`.
2. **Config and guard** (tests first): default production; `create_app()` raises when `environment == "dev"` and `K_SERVICE` is set (AC7).
3. **Token verification**: tests create an EC P-256 key and sign tokens with PyJWT; the key source is an injectable callable, so tests make no network call. Implement: ES256 only (`none` and HS256 rejected), `kid` lookup with one refresh on a miss, `iss`, `aud` from `project_number`, 30 s leeway, lazy fetch with a short timeout, cache with a TTL, any failure → 401 (AC1, AC2).
4. **Owner check**: lower-cased comparison with `owner_email`; empty or unset → 403 for everyone, regardless of `settings/owner`; the unsigned email header is ignored; generic bodies; no email or token in logs (`caplog`) (AC3, AC4, AC5, AC11).
5. **Origin check** (ADR-0013): `Origin == "https://" + Host.lower()` for non-safe methods; `http://` + `Host` also in `dev` only; `X-Forwarded-Host` ignored; missing → 403; runs before auth so bad-origin unauthenticated POSTs are 403. Tests for the deterministic host, the hash host, foreign, missing, forwarded-only, and the `dev`/production scheme rule (AC6). The app has no POST route yet, so the tests mount a test-only POST route on a test app.
6. **Settings repository**: create-if-absent (`create()` catching `AlreadyExists`, no overwrite); `ensure_owner` runs after the first successful auth and is remembered per instance; a failure is logged without the email and does not change the response (AC9, AC10). Tests use the fake; none touches Firestore.
7. **Pages and routes**: every route lives on the protected router; the route-inventory test requests each registered route without a token (AC8). Templates and CSS per spec UX: viewport meta, `lang`, `header`/`nav`/`main`, current page marked, Sign out link to `/_gcp_iap/clear_login_cookie`, labels, focus style, 44 px rule for header links, 16 px base text, header wraps at 360 px, bounded centred column on desktop. Template and stylesheet tests (AC12–AC14).
8. **Infra**: the env vars in `cloud_run_web.tf` (secret through `value_source.secret_key_ref`); `terraform fmt -check` and `init -backend=false && validate` for `infra/app` (AC17).
9. **Docs**: UC-01 if needed; Divergence log; a one-line note in the app README or `config.py` docstring that local runs need `JOBFINDER_ENVIRONMENT=dev`.
10. Run `scripts/build.sh`, `scripts/test.sh`, `scripts/lint.sh` and paste the output; run the `verifier` subagent and quote its verdict. Open the PR (`Closes #70`) only on the owner's go-ahead.
11. After the owner deploys: AC15 and AC16 (screenshots at 360 and 1280 px; sign-in on a phone and a laptop; another account refused) and AC18 (cold start after 15 min idle, image size) are recorded in Proof. The verifier lists them as pending until then.

## Risks

| Risk | Mitigation |
|---|---|
| The owner secret is missing or unreadable → revision fails or everyone is refused | Value is already in Secret Manager (runbook step 5); the app fails closed; the owner opens the page right after deploy |
| JWK fetch is slow or `www.gstatic.com` unreachable | Lazy fetch with a short timeout, cached; failure → 401, never allow; `/health` does not depend on it, so the revision still becomes Ready |
| Firestore client slows cold start or grows the image past NFR-A1 | Lazy import inside the Firestore repository so `/health` and the auth path do not pay for it; AC18 measures against the #69 baseline (4.0 s, 58 MB); escalate to the owner if far above |
| `Host` seen by the app is not the host the browser used | Cloud Run passes it unchanged; unit tests cover both URL hosts; re-check on the first POST route (slice S1); ADR-0013 says to revisit if a rewriting proxy is added |
| Default `production` breaks local runs and old smoke tests | Tests use `dependency_overrides` or a test-token fixture; `JOBFINDER_ENVIRONMENT=dev` documented for local runs |
| A later route added without protection | Protected router by default plus the route-inventory test in CI |
| New dependencies with known vulnerabilities | `scripts/audit.sh` (needs network; CI step); check the lock result before the PR |
| Real owner email in fixtures or logs | Use `owner@example.test`; `caplog` assertions; gitleaks and review |

## Proof

Commands pasted into the PR: `scripts/build.sh`, `scripts/lint.sh`, `scripts/test.sh`.

| Acceptance criterion | Evidence |
|---|---|
| AC1, AC2 | `test_auth.py`: no token; wrong `aud`, `iss`, algorithm, `kid`, signature; expired (parametrised) |
| AC3, AC4, AC5 | `test_auth.py`: other email, spoofed header, owner (case-insensitive), empty owner setting with existing `settings/owner` |
| AC6 | `test_csrf.py`: foreign, missing, unauthenticated foreign, matching `Host` on two hosts, forwarded-only refused, `http://` in `dev` vs production |
| AC7 | `test_config.py`: `dev` + `K_SERVICE` raises; unset → production |
| AC8 | `test_routes.py`: route inventory |
| AC9, AC10 | `test_settings_repo.py` |
| AC11 | `caplog` and body assertions in `test_auth.py` |
| AC12, AC13, AC14 | `test_pages.py`: template and stylesheet structure |
| AC15, AC16 | Manual after deploy: screenshots at 360 px and 1280 px; sign-in on phone and laptop; other account refused (PR) |
| AC17 | `terraform validate` in `scripts/lint.sh` and CI |
| AC18 | Cloud Run `container/startup_latencies` after 15 min idle and image size, recorded here after deploy |

## Divergence log

(Filled during implementation.)
