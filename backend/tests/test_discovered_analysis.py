import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import main


class DiscoveredAnalysisTests(unittest.TestCase):
    def test_search_route_returns_combined_provider_response(self):
        paper = {
            "paper_id": "arxiv:2305.14314v1",
            "doi": None,
            "arxiv_id": "2305.14314v1",
            "arxiv_url": "https://arxiv.org/abs/2305.14314v1",
            "source": "arXiv",
            "title": "QLoRA",
            "authors": ["Author One"],
            "year": 2023,
            "venue": "arXiv preprint",
            "abstract": "Abstract",
            "type": "preprint",
            "doi_url": None,
            "publisher_url": "https://arxiv.org/abs/2305.14314v1",
            "pdf_url": "https://arxiv.org/pdf/2305.14314v1",
            "license_url": None,
            "full_text_available": True,
        }
        with patch.object(main, "search_papers", return_value=([paper], [])):
            with TestClient(main.app) as client:
                response = client.post("/search", json={"query": "QLoRA"})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["papers"][0]["full_text_available"])
        self.assertEqual(response.json()["warnings"], [])

    def test_selected_arxiv_pdf_enters_existing_analysis_pipeline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(main, "UPLOAD_DIR", Path(temp_dir)),
                patch.object(main, "download_arxiv_paper", return_value=b"%PDF-1.7 test"),
                patch.object(main, "_run_analysis", return_value=None),
            ):
                with TestClient(main.app) as client:
                    response = client.post(
                        "/analyze-discovered",
                        json={"arxiv_ids": ["2305.14314v1"]},
                    )

            self.assertEqual(response.status_code, 200, response.text)
            job_id = response.json()["job_id"]
            job = main.jobs.pop(job_id)
            session = main.sessions.pop(job["session_id"])
            self.assertEqual(session["filenames"], ["arxiv_2305.14314v1.pdf"])
            self.assertEqual(Path(session["pdf_paths"][0]).read_bytes(), b"%PDF-1.7 test")

    def test_duplicate_arxiv_ids_are_rejected(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/analyze-discovered",
                json={"arxiv_ids": ["2305.14314v1", "2305.14314v1"]},
            )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
