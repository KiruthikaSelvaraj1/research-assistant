"""Paper discovery using the public Crossref works API."""
from __future__ import annotations

import html
import json
import logging
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from fastapi import HTTPException

_CROSSREF_WORKS_URL = "https://api.crossref.org/works"
_ARXIV_QUERY_URL = "https://export.arxiv.org/api/query"
_USER_AGENT = "AIResearchAssistant/1.0 (scholarly paper discovery)"
_MAX_PDF_BYTES = 50 * 1024 * 1024
_ARXIV_ID_PATTERN = re.compile(
    r"(?:\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)",
    re.IGNORECASE,
)
_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"
_LOGGER = logging.getLogger(__name__)
_SELECT_FIELDS = ",".join(
    (
        "DOI",
        "title",
        "author",
        "container-title",
        "published-print",
        "published-online",
        "published",
        "type",
        "URL",
        "link",
        "abstract",
        "license",
    )
)


def _plain_text(value: str) -> str:
    if not isinstance(value, str):
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(text).split())


def _web_url(value: object) -> str | None:
    if isinstance(value, str) and value.startswith(("https://", "http://")):
        return value
    return None


def _arxiv_id_from_doi(doi: str) -> str | None:
    prefix = "10.48550/arxiv."
    if doi.casefold().startswith(prefix):
        candidate = doi[len(prefix):]
        return candidate if _ARXIV_ID_PATTERN.fullmatch(candidate) else None
    return None


def _publication_year(item: dict) -> int | None:
    for field in ("published-print", "published-online", "published"):
        publication = item.get(field) or {}
        date_parts = publication.get("date-parts", [])
        if date_parts and date_parts[0] and isinstance(date_parts[0][0], int):
            return date_parts[0][0]
    return None


def _format_paper(item: dict) -> dict | None:
    titles = item.get("title") or []
    title = _plain_text(titles[0]) if titles else ""
    doi = item.get("DOI")
    if not title or not isinstance(doi, str):
        return None
    arxiv_id = _arxiv_id_from_doi(doi)

    authors = []
    for author in item.get("author", []):
        name = " ".join(
            part for part in (author.get("given"), author.get("family")) if part
        )
        if name:
            authors.append(name)

    direct_pdf_urls = [
        _web_url(link.get("URL"))
        for link in item.get("link", [])
        if (link.get("content-type") or "").casefold() == "application/pdf"
    ]
    licenses = [
        _web_url(license_item.get("URL"))
        for license_item in item.get("license", [])
    ]
    direct_pdf_urls = [url for url in direct_pdf_urls if url]
    licenses = [url for url in licenses if url]
    abstracts = item.get("abstract") or ""
    if isinstance(abstracts, list):
        abstracts = abstracts[0] if abstracts else ""

    return {
        "paper_id": doi,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "source": "Crossref",
        "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
        "title": title,
        "authors": authors[:8],
        "year": _publication_year(item),
        "venue": _plain_text((item.get("container-title") or [""])[0]),
        "abstract": _plain_text(abstracts)[:4_000] if abstracts else "",
        "type": item.get("type", "research output"),
        "doi_url": f"https://doi.org/{doi}",
        "publisher_url": _web_url(item.get("URL")) or f"https://doi.org/{doi}",
        "pdf_url": (
            f"https://arxiv.org/pdf/{arxiv_id}"
            if arxiv_id
            else direct_pdf_urls[0] if direct_pdf_urls else None
        ),
        "license_url": licenses[0] if licenses else None,
        "full_text_available": arxiv_id is not None,
    }


def _search_crossref(query: str, limit: int) -> list[dict]:
    params = urlencode({
        "query.bibliographic": query,
        "rows": limit,
        "select": _SELECT_FIELDS,
        "sort": "relevance",
        "order": "desc",
    })
    request = Request(
        f"{_CROSSREF_WORKS_URL}?{params}",
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )

    try:
        with urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Paper search provider returned HTTP {exc.code}. Please try again.",
        ) from exc
    except (TimeoutError, URLError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Paper search is temporarily unavailable. Please try again.",
        ) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Paper search provider returned an unreadable response.",
        ) from exc

    message = payload.get("message")
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list):
        raise HTTPException(
            status_code=502,
            detail="Paper search provider returned an invalid result list.",
        )

    papers = []
    for item in items:
        if isinstance(item, dict):
            paper = _format_paper(item)
            if paper:
                papers.append(paper)
    return papers


def _search_arxiv(query: str, limit: int) -> list[dict]:
    params = urlencode({
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": limit,
        "sortBy": "relevance",
        "sortOrder": "descending",
    })
    request = Request(
        f"{_ARXIV_QUERY_URL}?{params}",
        headers={"User-Agent": _USER_AGENT, "Accept": "application/atom+xml"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            root = ET.fromstring(response.read())
    except HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"arXiv search provider returned HTTP {exc.code}. Please try again.",
        ) from exc
    except (TimeoutError, URLError) as exc:
        raise HTTPException(
            status_code=502,
            detail="arXiv search is temporarily unavailable. Please try again.",
        ) from exc
    except (ET.ParseError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="arXiv search provider returned an unreadable response.",
        ) from exc

    papers = []
    for entry in root.findall(f"{_ATOM}entry"):
        entry_id = entry.findtext(f"{_ATOM}id", "") or ""
        arxiv_id = urlparse(entry_id).path.rsplit("/", 1)[-1]
        if not _ARXIV_ID_PATTERN.fullmatch(arxiv_id):
            continue
        title = _plain_text(entry.findtext(f"{_ATOM}title", ""))
        if not title:
            continue

        published = entry.findtext(f"{_ATOM}published", "") or ""
        doi = entry.findtext(f"{_ARXIV}doi")
        authors = [
            _plain_text(author.findtext(f"{_ATOM}name", ""))
            for author in entry.findall(f"{_ATOM}author")
        ]
        authors = [author for author in authors if author]
        papers.append({
            "paper_id": f"arxiv:{arxiv_id}",
            "doi": doi,
            "arxiv_id": arxiv_id,
            "source": "arXiv",
            "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
            "title": title,
            "authors": authors[:8],
            "year": int(published[:4]) if published[:4].isdigit() else None,
            "venue": "arXiv preprint",
            "abstract": _plain_text(entry.findtext(f"{_ATOM}summary", ""))[:4_000],
            "type": "preprint",
            "doi_url": f"https://doi.org/{doi}" if doi else None,
            "publisher_url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "license_url": None,
            "full_text_available": True,
        })
    return papers


def search_papers(query: str, limit: int = 10) -> tuple[list[dict], list[str]]:
    """Search Crossref and arXiv; report individual provider failures to the caller."""
    results: dict[str, list[dict]] = {}
    warnings = []
    providers = {
        "Crossref": _search_crossref,
        "arXiv": _search_arxiv,
    }
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending = {
            executor.submit(
                searcher,
                query,
                min(max(limit * 5, 50), 100) if provider == "arXiv" else limit,
            ): provider
            for provider, searcher in providers.items()
        }
        for future, provider in pending.items():
            try:
                results[provider] = future.result()
            except HTTPException as exc:
                _LOGGER.warning("%s paper search failed: %s", provider, exc.detail)
                warnings.append(exc.detail)

    if not results:
        raise HTTPException(
            status_code=502,
            detail="Paper search providers are unavailable. Please try again.",
        )

    merged: list[dict] = []
    seen_titles: dict[str, int] = {}
    crossref_papers = results.get("Crossref", [])
    arxiv_papers = results.get("arXiv", [])
    for index in range(max(len(crossref_papers), len(arxiv_papers))):
        for provider_papers in (crossref_papers, arxiv_papers):
            if index >= len(provider_papers):
                continue
            paper = provider_papers[index]
            normalized_title = re.sub(r"[^a-z0-9]+", "", paper["title"].casefold())
            existing_index = seen_titles.get(normalized_title)
            if existing_index is not None:
                existing = merged[existing_index]
                if paper.get("arxiv_id") and not existing.get("arxiv_id"):
                    existing.update(
                        arxiv_id=paper["arxiv_id"],
                        arxiv_url=paper["arxiv_url"],
                        pdf_url=paper["pdf_url"],
                        full_text_available=True,
                        source=f"{existing['source']} + arXiv",
                    )
                continue
            seen_titles[normalized_title] = len(merged)
            merged.append(paper)
            if len(merged) >= limit:
                return merged, warnings
    return merged, warnings


def download_arxiv_paper(arxiv_id: str) -> bytes:
    """Download a size-limited PDF using a validated arXiv identifier only."""
    if not _ARXIV_ID_PATTERN.fullmatch(arxiv_id):
        raise HTTPException(422, "Invalid arXiv identifier.")

    request = Request(
        f"https://arxiv.org/pdf/{quote(arxiv_id, safe='./')}",
        headers={"User-Agent": _USER_AGENT, "Accept": "application/pdf"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            host = urlparse(response.geturl()).hostname
            if host not in {"arxiv.org", "export.arxiv.org"}:
                raise HTTPException(
                    status_code=502,
                    detail=f"arXiv redirected to an unexpected host for {arxiv_id}.",
                )
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > _MAX_PDF_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"The PDF for arXiv:{arxiv_id} exceeds the 50 MB limit.",
                )
            content = response.read(_MAX_PDF_BYTES + 1)
    except HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"arXiv could not provide the PDF for {arxiv_id} (HTTP {exc.code}).",
        ) from exc
    except (TimeoutError, URLError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not download the arXiv PDF for {arxiv_id}. Please try again.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"arXiv returned an invalid content length for {arxiv_id}.",
        ) from exc

    if len(content) > _MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"The PDF for arXiv:{arxiv_id} exceeds the 50 MB limit.",
        )
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=502,
            detail=f"arXiv did not return a valid PDF for {arxiv_id}.",
        )
    return content
