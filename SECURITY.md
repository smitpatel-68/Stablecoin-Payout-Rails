# Security Policy

This repository is a product case study for a multi-chain stablecoin payout
platform. It contains specifications, design documents, and Python simulators —
**no production code, no real credentials, and no live infrastructure**.

Even so, because the domain is financial payments, we take security reports
seriously and prefer to hear about any issue — real or potential — before it
becomes a problem for anyone reusing the patterns documented here.

## Scope

In scope:

- Leaked secrets, keys, tokens, or credentials anywhere in the repo history
- Design flaws in the OpenAPI spec (`api-spec/openapi.yaml`) that would be
  exploitable if implemented verbatim
- Bugs in the Python simulators (`simulator/*.py`) that could cause incorrect
  compliance or routing decisions
- Misleading guidance in the compliance / workflow docs that could lead an
  implementer to ship a non-compliant system

Out of scope:

- "The simulator uses `random` for risk scoring" — this is intentional; see the
  docstrings. IDs and transaction-hash placeholders use `secrets`.
- "The OpenAPI `servers:` URL points to `api.yourcompany.com`" — that's a
  placeholder, not a live host.

## Reporting a vulnerability

Please **do not** file a public GitHub issue for security reports.

Instead, open a private GitHub security advisory against this repository:
<https://github.com/smitpatel-68/Stablecoin-Payout-Rails/security/advisories/new>

Include:

1. A description of the issue and the file / line that contains it
2. A proof of concept or exploitation scenario, if applicable
3. Your suggested remediation, if you have one
4. Whether you would like to be credited in the fix

We will acknowledge your report within 3 business days and aim to provide a
resolution (fix, documentation update, or explicit "won't fix" with rationale)
within 30 days.

## Supported versions

This is an evolving case study, not a released product. Only the `main` branch
is "supported" — fixes land there and older branches are not backported.

## Secret handling

No real secrets should ever be committed to this repository. If you see
something that looks like a key, token, private key, mnemonic, or credential,
please report it via the security advisory flow above — even if you think it
might be a placeholder. We would rather investigate a false positive than miss
a real leak.
