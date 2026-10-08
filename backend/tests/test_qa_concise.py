import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.qa import answer_from_sources


class _CapturingTask:
    description = ""

    def __init__(self, **kwargs):
        type(self).description = kwargs["description"]
        quote = (
            "QLoRA reduces memory usage by quantizing model weights to four bits "
            "while training low-rank adapters."
        )
        self.output = SimpleNamespace(
            raw=json.dumps({
                "answer": "QLoRA quantizes weights to four bits and trains low-rank adapters.",
                "citations": [{
                    "paper_index": 1,
                    "page": 1,
                    "quote": quote,
                }],
            })
        )


class _NoopCrew:
    def __init__(self, **_kwargs):
        pass

    def kickoff(self):
        pass


class AskPapersConciseTests(unittest.TestCase):
    def test_model_prompt_requests_brief_grounded_answers(self):
        sources = [{
            "paper_index": 1,
            "filename": "paper.pdf",
            "pages": [{
                "page": 1,
                "text": (
                    "QLoRA reduces memory usage by quantizing model weights to four bits "
                    "while training low-rank adapters."
                ),
            }],
        }]
        with (
            patch("backend.qa.Agent"),
            patch("backend.qa.Task", _CapturingTask),
            patch("backend.qa.Crew", _NoopCrew),
            patch("backend.crew.get_llm", return_value=object()),
        ):
            result = answer_from_sources(
                "How does QLoRA reduce memory usage?",
                sources,
            )

        self.assertFalse(result["abstained"])
        self.assertEqual(len(result["citations"]), 1)
        self.assertIn("2-4 sentences", _CapturingTask.description)
        self.assertIn("60-100 words", _CapturingTask.description)


if __name__ == "__main__":
    unittest.main()
