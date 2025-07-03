# Keystone-Graphing

Creates three JPEG dashboards from Jira issues and posts them to Slack every
second Thursday at 06:00 ET via GitHub Actions.  Run the same script locally
with **uv** for rapid tweaks.

## Quick start (local)

```bash
brew install astral-sh/uv/uv        # or: pipx install uv
git clone YOUR_FORK jira-reporting && cd jira-reporting
uv venv .venv && uv pip install -r requirements.txt
cp .env.example .env                # fill in your secrets
./generate_graphs.py --show         # opens preview windows