"""HackBio "Build AI Agents for Biology" - literature review agent.

Searches PubMed through NCBI E-utilities, fetches the matching abstracts,
and asks Claude to write a cited literature review that answers a
research question.

Usage:
    python literature_agent.py "What is the role of TP53 in glioblastoma?"
    python literature_agent.py "CRISPR off-target effects" --query "CRISPR[tiab] AND off-target[tiab]" -n 15
"""

import argparse
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import anthropic
import requests
from dotenv import load_dotenv

load_dotenv()

PUBMED_SEARCH_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
)

PUBMED_FETCH_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
)

# NCBI asks every E-utilities caller to identify itself with an email and tool name.
NCBI_EMAIL = os.getenv("NCBI_EMAIL", "kwena@anewk.io")
NCBI_TOOL = "hackbio_litrature_review_agent"
# Optional: an NCBI API key raises the rate limit from 3 to 10 requests/second.
NCBI_API_KEY = os.getenv("NCBI_API_KEY")

# The model and effort can be changed without editing the program.
MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("CLAUDE_EFFORT", "medium")

# Models that accept server-side refusal fallbacks (`fallbacks: "default"`).
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """You are a biomedical literature review assistant.

You receive a research question and a set of PubMed records (title, journal,
year, authors, abstract). Write a concise, well-structured literature review
in Markdown that answers the question using only the supplied records.

- Open with a 2-3 sentence answer to the question.
- Group findings by theme, noting where studies agree, disagree, or differ in
  organism, sample size, or method.
- Cite every claim with the PubMed ID in square brackets, e.g. [PMID:12345678].
- Point out gaps, limitations, and open questions.
- If the records do not answer the question, say so plainly rather than
  filling in from general knowledge.
- End with a "References" list: PMID, first author, year, title."""


@dataclass
class Article:
    pmid: str
    title: str
    abstract: str
    journal: str = ""
    year: str = ""
    authors: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"


def _ncbi_params(**extra) -> dict:
    params = {"tool": NCBI_TOOL, "email": NCBI_EMAIL, **extra}
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    return params


def search_pubmed(query: str, max_results: int = 10) -> list[str]:
    """Return PubMed IDs for a query, most relevant first."""
    response = requests.get(
        PUBMED_SEARCH_URL,
        params=_ncbi_params(
            db="pubmed", term=query, retmax=max_results, retmode="json", sort="relevance"
        ),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["esearchresult"]["idlist"]


def fetch_articles(pmids: list[str]) -> list[Article]:
    """Fetch titles, abstracts and metadata for a list of PubMed IDs."""
    if not pmids:
        return []
    response = requests.get(
        PUBMED_FETCH_URL,
        params=_ncbi_params(db="pubmed", id=",".join(pmids), retmode="xml"),
        timeout=60,
    )
    response.raise_for_status()
    return parse_pubmed_xml(response.text)


def _text(element) -> str:
    # itertext() keeps text inside inline markup such as <i>, <sup>, <sub>.
    return "".join(element.itertext()).strip() if element is not None else ""


def parse_pubmed_xml(xml_text: str) -> list[Article]:
    """Parse an efetch PubmedArticleSet document into Article records."""
    root = ET.fromstring(xml_text)
    articles = []
    for record in root.iter("PubmedArticle"):
        sections = []
        for part in record.findall(".//Abstract/AbstractText"):
            text = _text(part)
            label = part.get("Label")
            if text:
                sections.append(f"{label}: {text}" if label else text)

        pub_date = record.find(".//JournalIssue/PubDate")
        year = ""
        if pub_date is not None:
            year = pub_date.findtext("Year") or (pub_date.findtext("MedlineDate") or "")[:4]

        authors = []
        for author in record.findall(".//AuthorList/Author"):
            if author.findtext("CollectiveName"):
                authors.append(author.findtext("CollectiveName"))
            elif author.findtext("LastName"):
                authors.append(f"{author.findtext('LastName')} {author.findtext('Initials') or ''}".strip())

        articles.append(
            Article(
                pmid=record.findtext(".//MedlineCitation/PMID", default=""),
                title=_text(record.find(".//ArticleTitle")),
                abstract="\n".join(sections),
                journal=record.findtext(".//Journal/Title", default=""),
                year=year,
                authors=authors,
            )
        )
    return articles


def format_articles(articles: list[Article]) -> str:
    """Render articles as tagged blocks for the prompt."""
    blocks = []
    for a in articles:
        authors = ", ".join(a.authors[:3]) + (" et al." if len(a.authors) > 3 else "")
        blocks.append(
            f'<article pmid="{a.pmid}">\n'
            f"Title: {a.title}\n"
            f"Journal: {a.journal} ({a.year})\n"
            f"Authors: {authors}\n"
            f"Abstract:\n{a.abstract or '(no abstract available)'}\n"
            f"</article>"
        )
    return "\n\n".join(blocks)


def review_literature(
    question: str, articles: list[Article], client: anthropic.Anthropic | None = None
) -> str:
    """Ask Claude for a cited literature review of the supplied articles."""
    client = client or anthropic.Anthropic()

    extra = {}
    if MODEL in FALLBACK_MODELS:
        # If a safety classifier declines, the API re-runs the request on
        # Anthropic's recommended fallback model inside the same call.
        extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"}

    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        output_config={"effort": EFFORT},
        messages=[
            {
                "role": "user",
                "content": f"<articles>\n{format_articles(articles)}\n</articles>\n\n"
                f"Research question: {question}",
            }
        ],
        **extra,
    )

    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined the request: {response.stop_details}")
    return "".join(block.text for block in response.content if block.type == "text")


def run_agent(question: str, query: str | None = None, max_results: int = 10) -> str:
    """Search PubMed, fetch abstracts, and return a Markdown literature review."""
    pmids = search_pubmed(query or question, max_results=max_results)
    if not pmids:
        return f"No PubMed results for: {query or question}"
    articles = fetch_articles(pmids)
    return review_literature(question, articles)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("question", help="Research question to answer")
    parser.add_argument("--query", help="PubMed search query (defaults to the question)")
    parser.add_argument("-n", "--max-results", type=int, default=10, help="Number of articles to review")
    args = parser.parse_args()
    print(run_agent(args.question, query=args.query, max_results=args.max_results))


if __name__ == "__main__":
    main()
