# Agentic AI assessment: extend the Document Agent - how to submit

## At a glance
- Build: extend the Document Agent: add a tool, make it observable, SQLite chat memory, one shared knowledge base (see `docs/TASK.md`)
- Window: **the opening time your instructor announced** to **the closing time your instructor announced** (judged on when your GitHub Actions run finishes)
- Pass: **all 10 points** (every task is required; partial scores are recorded too)
- You may submit as many times as you like; **your best score is kept**
- Result arrives by **email** (check spam)

## What you need
- GitHub account (free)
- Google account (the form asks you to sign in; your result goes to that email)
- Git, Docker, and [uv](https://docs.astral.sh/uv/getting-started/installation/) installed (setup: `README.md`)
- You do **not** need your Groq key for the submission: GitHub runs your code with a scripted model

## Steps

### 1. Create your repo
- Open the template repository link your instructor shared (named `matrimorphosis-agentic-ai-assessment`) then **Use this template** then **Create a new repository**
- Owner: **your own account** (not an organisation)
- Visibility: **Private**
- Clone it:
  ```bash
  git clone https://github.com/<you>/<your-repo>
  cd <your-repo>
  ```

### 2. Set up and turn on the local checks (once)
Follow `README.md` (Groq key, `bash scripts/check_setup.sh`, `docker compose up --build -d`), then:
```bash
uv run --only-group hooks pre-commit install
```
- Before each commit: blocks changes to locked files
- Before each push: also runs the autograder locally in Docker (a few minutes)
- In a hurry? `git push --no-verify` skips the local run; the GitHub Action is the real grader

### 3. Write your solution
- Edit **only `src/app/`** (`README.md` and `.gitignore` are also free)
- Everything else is locked and compared with the template, byte for byte:
  - `tests/`, `Dockerfile`, `pyproject.toml`, `uv.lock`, `docker-compose.yml`, `.env.example`, `.github/`, `scripts/`, `docs/`, `data/`, `samples/`, `ui/`, `mcp_server/`, `observability/`, `.pre-commit-config.yaml`, `.checksums`, `.gitattributes`
- Adding, deleting or changing any locked file makes the submission invalid
- If a commit is blocked, the message lists the files; fix with:
  ```bash
  git restore --staged --worktree <file>      # changed or deleted file
  git rm -f --cached <file> && rm <file>      # file you should not have added
  ```

### 4. Check locally
```bash
bash scripts/local_eval.sh       # the full autograder: scripted model, restart, second phase. Prints PASS/FAIL per check
```

### 5. Push and wait for the run
```bash
git add -A && git commit -m "my solution" && git push origin main
```
- Push to **`main`** only
- Open the **Actions** tab, wait for the run named **evaluate** to finish (green tick or red cross are both fine; it takes about 5-10 minutes)
- The run's log shows your score and one PASS/FAIL line per check
- Copy the run URL: `https://github.com/<you>/<repo>/actions/runs/<number>`

### 6. Create a read-only token
GitHub, then **Settings, Developer settings, Personal access tokens, Fine-grained tokens, Generate new token**

| Field | Value |
|---|---|
| Expiration | 7 days |
| Resource owner | your own account |
| Repository access | **Only select repositories**, then your repo |
| Permissions | **Actions: Read**, **Contents: Read** (Metadata: Read is added automatically) |

- Copy the token (starts with `github_pat_`); GitHub shows it once

### 7. Submit the form
- Open the submission form link your instructor shared and sign in with Google
- Fill: name, run URL, token
- Submit; your response (including the token) is **deleted automatically** right after verification
- After you get your result email, **revoke the token** on GitHub (Settings, Fine-grained tokens, Delete)

## What gets checked
- The run is from the official **evaluate** workflow, a **push to `main`** of **your** repo
- Every locked file (everything except `src/app/`, `README.md`, `.gitignore`) equals the template at that commit
- The run finished inside the window
- Test results belong to this assessment and to the same commit
- One GitHub account per Google email (do not share repos or tokens)
- Solutions are compared across students; matching code is flagged for review

## Scoring
| Check | Points |
|---|---|
| Your new tool is registered with the agent (`tool-registered`) | 1 |
| Your tool works with valid arguments (`tool-works`) | 1 |
| Your tool reports bad input as ERROR[CODE] (`tool-errors`) | 1 |
| Your tool records its own metric (`tool-metric`) | 1 |
| Your tool writes a structured log line (`tool-log`) | 1 |
| Upload, ingest, search and citations still work (`baseline`) | 1 |
| A document uploaded in one chat is searchable from another (`shared-kb`) | 1 |
| The shared knowledge base survives a restart (`kb-persists`) | 1 |
| Chat memory survives a restart (SQLite checkpointer) (`sqlite-memory`) | 2 |

## If something goes wrong
The email says what failed. Common ones:

| Email says | Check |
|---|---|
| Token was not accepted | copied fully, not expired, belongs to the account that owns the repo |
| Could not open your repository | token's repository access includes this repo; Actions, Contents, Metadata set to Read |
| Run does not exist | URL copied from your repo's Actions tab |
| Run not finished | wait for the green tick or red cross, then resubmit |
| Not from the official workflow | submit the **evaluate** run; do not add or edit `.github/workflows/` |
| Not a normal push to main | push to `main`; do not use manual or pull-request runs |
| Files outside src/app/ changed | restore the listed files, push, submit the **new** run |
| Outside the submission window | contact the instructor |
| No test results | re-run the workflow, then submit the new run |
| Account already registered with another email | use your original Google account, or contact the instructor |

An invalid submission records **no score** and never lowers an earlier one. Fix, push, and submit the new run URL.

## Contact
Your instructor (the contact in the course channel).
