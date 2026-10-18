
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agents.technology import TechnologyAgent


class TechnologyAgentTests(unittest.TestCase):

    @patch("agents.technology.graph")
    def test_empty_question_is_rejected(self, mock_graph):
        agent = TechnologyAgent()

        for question in ("", "  ", None):
            with self.subTest(question=question):
                with self.assertRaises(ValueError):
                    agent.run(question)

        mock_graph.invoke.assert_not_called()

    @patch("agents.technology.graph")
    def test_question_routes_to_technology(self, mock_graph):
        mock_graph.invoke.return_value = {
            "answer": "Cisco ASR 1000 supports WAN aggregation.",
            "context": [],
        }

        agent = TechnologyAgent()

        result = agent.run(
            "What are Cisco ASR 1000 capabilities?"
        )

        self.assertEqual(result["domain"], "technology")
        self.assertEqual(
            result["answer"],
            "Cisco ASR 1000 supports WAN aggregation."
        )

        mock_graph.invoke.assert_called_once_with({
            "question": "What are Cisco ASR 1000 capabilities?",
            "domain": "technology",
        })

    @patch("agents.technology.graph")
    def test_evidence_and_page_numbers_are_preserved(
        self, mock_graph
    ):
        mock_graph.invoke.return_value = {
            "answer": "Cisco ASR 1000 supports high availability.",
            "context": [
                SimpleNamespace(
                    page_content="Hardware redundancy is supported.",
                    metadata={
                        "source": "cisco-asr-1000.pdf",
                        "page": 5,
                    },
                )
            ],
        }

        agent = TechnologyAgent()

        result = agent.run(
            "What redundancy does Cisco ASR 1000 support?"
        )

        self.assertEqual(
            result["sources"][0]["document"],
            "cisco-asr-1000.pdf"
        )

        # PDF page indexes start at zero
        self.assertEqual(result["sources"][0]["page"], 6)

        self.assertEqual(
            result["answer"],
            "Cisco ASR 1000 supports high availability."
        )

    @patch("agents.technology.graph")
    def test_no_documents_returns_empty_sources(
        self, mock_graph
    ):
        mock_graph.invoke.return_value = {
            "answer": "No relevant documents were found.",
            "context": [],
        }

        agent = TechnologyAgent()

        result = agent.run(
            "What are Cisco router specifications?"
        )

        self.assertEqual(result["sources"], [])
        self.assertEqual(
            result["answer"],
            "No relevant documents were found."
        )

    @patch("agents.technology.graph")
    def test_missing_page_metadata(self, mock_graph):
        mock_graph.invoke.return_value = {
            "answer": "Cisco router information.",
            "context": [
                SimpleNamespace(
                    page_content="Cisco router information.",
                    metadata={"source": "cisco.pdf"},
                )
            ],
        }

        result = TechnologyAgent().run(
            "Tell me about Cisco routers"
        )

        self.assertIsNone(result["sources"][0]["page"])


if __name__ == "__main__":
    unittest.main()
