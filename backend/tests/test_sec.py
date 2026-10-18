import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from agents.sec import SECAgent


class SECAgentTests(unittest.TestCase):
    def test_empty_collection_does_not_call_model(self):
        store = Mock()
        store.similarity_search.return_value = []
        client = Mock()
        result = SECAgent(client, store).analyze("What are Cisco's risks?")
        self.assertEqual(result["status"], "insufficient_evidence")
        client.responses.create.assert_not_called()

    def test_evidence_and_page_numbers_are_preserved(self):
        store = Mock()
        store.similarity_search.return_value = [SimpleNamespace(
            page_content="Competition may reduce margins.",
            metadata={"source": "cisco-2025.pdf", "page": 9},
        )]
        client = Mock()
        client.responses.create.return_value.output_text = "Margin risk [S1]."
        result = SECAgent(client, store).analyze("Cisco risks", k=5)
        self.assertEqual(result["sources"][0]["page"], 10)
        self.assertEqual(result["answer"], "Margin risk [S1].")
        request = client.responses.create.call_args.kwargs
        self.assertEqual(json.loads(request["input"])["evidence"], result["sources"])
        self.assertFalse(request["store"])
        store.similarity_search.assert_called_once_with("Cisco risks", k=5)

    def test_invalid_input_is_rejected_before_retrieval(self):
        agent = SECAgent(vector_store=Mock())
        for question in ("", "  ", None):
            with self.assertRaises(ValueError):
                agent.analyze(question)
        for k in (0, 21, True, 1.5):
            with self.assertRaises(ValueError):
                agent.analyze("Cisco risks", k=k)
        agent.vector_store.similarity_search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
