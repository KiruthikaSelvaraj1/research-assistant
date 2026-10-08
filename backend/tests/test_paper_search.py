import io
import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from fastapi import HTTPException

from backend.paper_search import (
    _search_crossref,
    _search_arxiv,
    download_arxiv_paper,
    search_papers,
)


class PaperSearchTests(unittest.TestCase):
    def test_search_crossref_normalizes_metadata(self):
        item = {
            "DOI": "10.1234/example",
            "title": ["A <i>useful</i> paper"],
            "author": [{"given": "Ada", "family": "Researcher"}],
            "published-online": {"date-parts": [[2024, 3, 2]]},
            "container-title": ["Journal of Tests"],
            "abstract": "<jats:p>Evidence &amp; methods.</jats:p>",
            "URL": "https://publisher.example/record",
            "link": [
                {
                    "content-type": "application/pdf",
                    "URL": "https://publisher.example/paper.pdf",
                }
            ],
        }
        response_data = json.dumps({"message": {"items": [item]}}).encode()

        with patch(
            "backend.paper_search.urlopen",
            return_value=io.BytesIO(response_data),
        ) as open_url:
            papers = _search_crossref("research topic", limit=2)

        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["title"], "A useful paper")
        self.assertEqual(papers[0]["source"], "Crossref")
        self.assertEqual(papers[0]["authors"], ["Ada Researcher"])
        self.assertEqual(papers[0]["year"], 2024)
        self.assertEqual(papers[0]["abstract"], "Evidence & methods.")
        self.assertEqual(
            papers[0]["pdf_url"], "https://publisher.example/paper.pdf"
        )
        params = parse_qs(urlsplit(open_url.call_args.args[0].full_url).query)
        self.assertEqual(params["query.bibliographic"], ["research topic"])
        self.assertEqual(params["rows"], ["2"])

    def test_omits_records_without_doi_or_title(self):
        response_data = json.dumps({
            "message": {
                "items": [
                    {"DOI": "10.1234/no-title"},
                    {"title": ["No DOI"]},
                ]
            }
        }).encode()

        with patch(
            "backend.paper_search.urlopen",
            return_value=io.BytesIO(response_data),
        ):
            self.assertEqual(_search_crossref("research topic", 10), [])

    def test_search_adds_arxiv_access_to_matching_crossref_record(self):
        crossref_paper = {
            "paper_id": "10.1234/example",
            "doi": "10.1234/example",
            "source": "Crossref",
            "title": "Matching Paper",
            "full_text_available": False,
            "arxiv_id": None,
        }
        arxiv_paper = {
            "paper_id": "arxiv:2305.14314v1",
            "source": "arXiv",
            "title": "Matching Paper",
            "arxiv_id": "2305.14314v1",
            "arxiv_url": "https://arxiv.org/abs/2305.14314v1",
            "pdf_url": "https://arxiv.org/pdf/2305.14314v1",
            "full_text_available": True,
        }
        with (
            patch(
                "backend.paper_search._search_crossref",
                return_value=[crossref_paper],
            ),
            patch(
                "backend.paper_search._search_arxiv",
                return_value=[arxiv_paper],
            ),
        ):
            papers, warnings = search_papers("Matching Paper", 10)

        self.assertEqual(len(papers), 1)
        self.assertTrue(papers[0]["full_text_available"])
        self.assertEqual(papers[0]["arxiv_id"], "2305.14314v1")
        self.assertEqual(papers[0]["source"], "Crossref + arXiv")
        self.assertEqual(warnings, [])

    def test_arxiv_search_returns_analyzable_preprints(self):
        feed = b"""<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:arxiv="http://arxiv.org/schemas/atom">
          <entry>
            <id>http://arxiv.org/abs/2305.14314v1</id>
            <title>QLoRA: <i>Efficient</i> Finetuning</title>
            <published>2023-05-23T17:50:33Z</published>
            <summary> A useful abstract. </summary>
            <author><name>Author One</name></author>
            <arxiv:doi>10.48550/arXiv.2305.14314</arxiv:doi>
          </entry>
        </feed>"""
        with patch(
            "backend.paper_search.urlopen",
            return_value=io.BytesIO(feed),
        ):
            papers = _search_arxiv("QLoRA", 5)

        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["arxiv_id"], "2305.14314v1")
        self.assertEqual(papers[0]["doi"], "10.48550/arXiv.2305.14314")
        self.assertTrue(papers[0]["full_text_available"])
        self.assertEqual(
            papers[0]["pdf_url"], "https://arxiv.org/pdf/2305.14314v1"
        )

    def test_arxiv_pdf_download_validates_identifier_and_pdf_bytes(self):
        class PdfResponse(io.BytesIO):
            headers = {"Content-Length": "9"}

            @staticmethod
            def geturl():
                return "https://arxiv.org/pdf/2305.14314v1"

        with patch(
            "backend.paper_search.urlopen",
            return_value=PdfResponse(b"%PDF-1.7"),
        ) as open_url:
            content = download_arxiv_paper("2305.14314v1")
        self.assertEqual(content, b"%PDF-1.7")
        self.assertIn("arxiv.org/pdf/2305.14314v1", open_url.call_args.args[0].full_url)

        with self.assertRaises(HTTPException):
            download_arxiv_paper("http://127.0.0.1/")


if __name__ == "__main__":
    unittest.main()
