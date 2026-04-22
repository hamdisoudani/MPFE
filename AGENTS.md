# Agent constraints

**Non-negotiable rules for any AI agent (or human) pushing to this repo.**

## Git identity

All commits to `hamdisoudani/MPFE` **must** be authored with:

| Field | Value |
|---|---|
| `user.name`  | `hamdisoudani` |
| `user.email` | `hamdisoudani.freelancer@gmail.com` |

Pushing with a different name or email is **forbidden**. Before the first commit in any session verify:

```bash
git config --global user.name   # -> hamdisoudani
git config --global user.email  # -> hamdisoudani.freelancer@gmail.com
```

The E2B `desktop` sandbox provisioned by `scripts/e2b_sandbox.py` already has this configured globally, plus env exports in `~/.env_mpfe` (sourced from `~/.bashrc`):

```
GIT_AUTHOR_NAME=hamdisoudani
GIT_AUTHOR_EMAIL=hamdisoudani.freelancer@gmail.com
GIT_COMMITTER_NAME=hamdisoudani
GIT_COMMITTER_EMAIL=hamdisoudani.freelancer@gmail.com
```

## Execution environment

All code runs in the E2B `desktop` sandbox. See `README.md` → "Execution environment" and `scripts/e2b_sandbox.py`.

- Tests, builds, migrations, `git push` — all via `sbx.commands.run(...)`.
- Never run project commands on the orchestrator VM itself.

## Credentials

- `E2B_API_KEY` and `GITHUB_PAT` are passed in per session. Never commit them.
- Inside the sandbox they live in `~/.env_mpfe` (chmod 600-ish) and `~/.netrc`. Those files are sandbox-local and do not leave it.
- `.e2b_sandbox.json` **is** committed — the sandbox id alone is useless without the API key, it just saves a `list()` round-trip on cold starts.

## Sandbox reuse policy

1. `Sandbox.list()` — reuse any RUNNING `desktop` sandbox on the account.
2. Else reconnect to the id in `.e2b_sandbox.json`.
3. Else create a new one with `timeout=3600`.

Never create a sandbox without running step 1 first.
