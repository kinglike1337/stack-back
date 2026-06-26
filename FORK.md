# stack-back — fork distribution

This is a **temporary downstream distribution** of
[`lawndoc/stack-back`](https://github.com/lawndoc/stack-back). It bundles a few
fixes/features that are still pending upstream into ready-to-use images, until
those changes are merged upstream — at which point this distribution will be
retired.

> Once all patches below have landed upstream, switch back to the official image:
> `ghcr.io/lawndoc/stack-back`.

## Image

```
ghcr.io/kinglike1337/stack-back
```

| Tag | Meaning |
|---|---|
| `edge` | rolling — always the latest bundled build |
| `<upstream-base>-fork.<N>` | e.g. `1.5.4-fork.1` — pinnable versioned build (base = the upstream release it sits on) |
| `sha-<short>` | exact commit, for debugging |

The `-fork.N` suffix is a SemVer prerelease, so these tags never collide with
real upstream versions and always sort below them.

## Included patches

| Change | Branch | Upstream status |
|---|---|---|
| Apprise notifications (replaces the SMTP/Discord backends) | `feat/apprise-notifications` | not yet submitted |
| Redact repository password from log output | `fix/redact-repo-password-in-logs` | PR [#114](https://github.com/lawndoc/stack-back/pull/114) |
| Bump vulnerable transitive Python deps | `chore/bump-vulnerable-python-deps` | not yet submitted |

## Usage (docker compose)

```yaml
services:
  backup:
    image: ghcr.io/kinglike1337/stack-back:1.5.4-fork.1   # or :edge
    # ... see the upstream docs for the rest of the configuration
```

## Tracking updates with What's Up Docker (WUD)

Track meaningful version bumps (recommended):

```yaml
labels:
  wud.tag.include: '^\d+\.\d+\.\d+-fork\.\d+$'
```

Or follow the rolling `edge` tag by digest:

```yaml
labels:
  wud.watch.digest: 'true'
```

## How this is maintained

Images are built by the `Fork Distribution Build` workflow from the `dist`
branch, which is rebuilt as `upstream/main` + the patch branches above. The
`main` branch tracks `upstream/main` unchanged.
