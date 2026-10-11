## What and why

<!-- What does this change, and why? Link the issue it closes. -->

## How I tested it

<!-- Commands run, manual steps, screenshots (use demo data only). -->

## Checklist

- [ ] Tests pass: `python manage.py test`; `makemigrations --check --dry-run` is clean
- [ ] New migrations are reversible
- [ ] New UI text uses `{% tr %}` and has a Russian translation
- [ ] Docs, `.env.example` and the configuration reference are updated; CHANGELOG has an *Unreleased* entry
- [ ] No secrets, personal data, real hostnames or IPs in the diff
- [ ] I touched a security-sensitive area (crypto, auth, sharing, uploads, settings, images/installers) and explained it above
