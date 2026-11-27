# ADR-0013: Origin check against the request's own host

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-27 |
| **Issue** | #70 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |
| **Supersedes** | ADR-0008, §5 (CSRF) of its decision only: the Origin rule and its list of service URLs |

## Context

[ADR-0008](0008-user-authentication.md) §5 requires every method other than GET, HEAD and OPTIONS to carry an `Origin` header that is in a configured list of the service's URLs, because IAP cookies are sent by the browser automatically. It notes that Cloud Run serves two URLs for the service, a deterministic `…-<project number>.us-central1.run.app` and an older hash URL (`…-uc.a.run.app`), and expects both to be listed or one to be disabled (#16).

The owner uses the hash URL. A list that holds only the deterministic URL, which the project number alone can produce, would refuse the owner's own requests; listing the hash URL needs a value that is known only after the first deploy and is not part of the Terraform inputs.

## Decision drivers

- NFR-S1: state-changing requests must not be forgeable from another site.
- Both Cloud Run URLs work without extra configuration; nothing to keep in sync with the deployment (ADR-0008: least code to write and get wrong).
- No new secret or configuration value.

## Options considered

### Option 1: configured list of the service's URLs (ADR-0008 §5 as written)

- Good: explicit.
- Bad: needs the hash URL or a decision to disable it; a list that drifts from the real URLs locks the owner out or leaves a URL unchecked.

### Option 2: `Origin` equals `"https://" + Host` of the same request

The browser sets `Origin` and a page on another site cannot make it equal to this service's own host; the request's `Host` is the host the browser addressed.

- Good: works on either Cloud Run URL and on a custom domain later, with no configuration.
- Bad: trusts the `Host` that Cloud Run and IAP pass on; `X-Forwarded-Host` must not be used.

## Decision

Option 2. This replaces only the Origin rule in ADR-0008 §5; everything else in ADR-0008 stands (IAP, JWT verification, owner email, `dev` mode rules, first sign-in).

1. Every method other than GET, HEAD and OPTIONS must carry an `Origin` header equal to `"https://" + Host` of the same request. The host is compared case-insensitively; `X-Forwarded-Host` is not used. A missing or different `Origin` answers **403**.
2. The check runs for all such requests, including those without a valid token.
3. There is no configured list of origins; the `allowed_origins` setting named in ADR-0008's follow-ups is not created.
4. Tests cover: foreign `Origin`, missing `Origin`, matching `Host` on the deterministic and the hash URL, an `Origin` that matches only `X-Forwarded-Host` (refused), and the scheme rule of point 5 (`http://` + `Host` accepted in `dev`, refused in production).
5. In `dev` mode only (local runs without TLS), `"http://" + Host` is accepted as well. Production accepts `https://` only. The mode is the one of ADR-0008 §6, which cannot start on Cloud Run.

## Consequences

- Positive: both service URLs work; no configuration to drift; less code.
- Negative: correctness depends on `Host` being the host the browser used. Cloud Run passes it unchanged; if a proxy that rewrites it is ever put in front, revisit this ADR.
- Follow-ups: #70 implements it (R4, AC6 of its spec). ADR-0008 is not edited; this ADR's Supersedes row, the ADR index and `CLAUDE.md` carry the link.
