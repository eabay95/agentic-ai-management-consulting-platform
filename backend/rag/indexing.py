"""Batched local indexing; stable IDs allow ingestion scripts to resume."""

BATCH_SIZE = 32


def add_batch(store, documents, ids):
    store.add_documents(documents=documents, ids=ids)
