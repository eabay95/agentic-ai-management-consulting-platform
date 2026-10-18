import unittest
from unittest.mock import Mock

from rag.indexing import add_batch


class IndexingTests(unittest.TestCase):
    def test_preserves_documents_and_stable_ids(self):
        store = Mock()
        add_batch(store, ["text"], ["stable-id"])
        store.add_documents.assert_called_once_with(documents=["text"], ids=["stable-id"])

    def test_storage_failures_propagate(self):
        store = Mock()
        store.add_documents.side_effect = ValueError("write failed")
        with self.assertRaises(ValueError):
            add_batch(store, [], [])
        self.assertEqual(store.add_documents.call_count, 1)
