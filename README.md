# HackBio literature review agent

A PubMed literature review agent built for the HackBio **"Build AI Agents for Biology"** course, using Anthropic's Claude (instead of the OpenAI GPT model in the course template).

It does three things:

1. Searches PubMed through NCBI E-utilities (`esearch`).
2. Fetches titles, abstracts and metadata for the top hits (`efetch`).
3. Sends them to Claude, which writes a Markdown literature review with `[PMID:…]` citations.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
```

Then put your Claude Platform API key in `.env` as `ANTHROPIC_API_KEY=...`. The `.env` file is git-ignored.

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | (none) | Claude Platform API key |
| `NCBI_EMAIL` | `kwena@anewk.io` | NCBI asks callers to identify themselves |
| `NCBI_API_KEY` | (none) | Optional; raises PubMed rate limit from 3 to 10 req/s |
| `CLAUDE_MODEL` | `claude-opus-5-5` | Any Claude model ID |
| `CLAUDE_EFFORT` | `medium` | `low` / `medium` / `high` / `xhigh` / `max` |

## Run

Command line:

```bash
python literature_agent.py "What is the role of TP53 mutations in glioblastoma treatment resistance?"
python literature_agent.py "CRISPR off-target effects" --query "CRISPR[tiab] AND off-target[tiab]" -n 15
```

Notebook: `jupyter lab notebooks/literature_review_agent.ipynb`

Tests (offline, no API key needed):

```bash
python -m unittest
```

## Notes

- Uses adaptive thinking and, on models that support it, server-side refusal fallbacks (`fallbacks: "default"`), so a declined request is re-run on Anthropic's recommended fallback model.
- `requirements.txt` is the course environment with `openai` → `anthropic` and `langchain-openai` → `langchain-anthropic`.
