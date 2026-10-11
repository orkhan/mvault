# Security policy

> mVault has not been independently audited. See [docs/security.md](docs/security.md) for the threat model and known limits.

mVault stores sensitive data, so security reports are taken seriously. Please read [docs/security.md](docs/security.md) for the threat model and known limits first.

## Supported versions

mVault is pre-1.0. Security fixes are made for the **latest released minor version** (and the `main` branch). Older versions are not patched; upgrade instead ([docs/upgrading.md](docs/upgrading.md)).

| Version | Supported |
|---|---|
| Latest release (0.x) | ✅ |
| Older releases | ❌ |

## Reporting a vulnerability

**Do not open a public issue.** Report privately through GitHub:

<https://github.com/orkhan/mvault/security/advisories/new>

Please include:

- what is affected (version or commit, install method) and the impact you see;
- clear steps to reproduce, or a proof of concept;
- any suggested fix.

**Never include real secrets, vault contents, encryption keys or `.env` files** in a report. Use test data. If you accidentally exposed a secret, rotate it first.

## What to expect

mVault is maintained by one person in their spare time, so these are goals, not guarantees:

- acknowledgement within about 7 days;
- an assessment and a plan within about 30 days for confirmed issues;
- a fix released as soon as practical, with credit in the advisory and changelog unless you prefer to stay anonymous;
- coordinated disclosure: please give a reasonable time to fix before publishing details.

## Scope

In scope: authentication and session handling, authorisation (sharing, admin/member boundaries), encryption at rest and key handling, file upload/download, injection and XSS, the container images and installers, and dependency vulnerabilities that are exploitable in mVault.

Out of scope: attacks that need prior control of the server, database or encryption key (documented limits), missing features such as end-to-end encryption or two-factor sign-in, denial of service by an already-authenticated administrator, and findings in third-party software that mVault does not ship.
