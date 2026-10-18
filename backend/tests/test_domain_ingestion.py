import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from langchain_core.documents import Document
import ingest_domains


class DomainIngestionTests(unittest.TestCase):
    def test_reference_lists_and_mislabeled_pdfs_are_not_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'references.txt'
            path.write_text('Product https://www.cisco.com/example', encoding='utf-8')
            self.assertEqual(ingest_domains.prepare_documents(path, 'technology')[0], [])
            path = Path(folder) / 'paper.pdf'
            path.write_text('NCT Number,Study Title\n123,trial', encoding='utf-8')
            docs, reason = ingest_domains.prepare_documents(path, 'clinical')
            self.assertEqual(docs, [])
            self.assertIn('Not a PDF', reason)

    def test_page_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'paper.pdf'
            path.write_bytes(b'%PDF-1.7 test fixture')
            with patch.object(ingest_domains, 'load_and_split', return_value=[Document(page_content='Clinical paper text', metadata={'page': 2})]):
                docs, reason = ingest_domains.prepare_documents(path, 'clinical')
            self.assertEqual(docs[0].metadata['page'], 2)
            self.assertEqual(docs[0].metadata['page_number'], 3)
            self.assertEqual(docs[0].metadata['domain'], 'clinical')

    def test_repeat_ingestion_skips_existing_chunks(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / 'data' / 'clinical'
            source.mkdir(parents=True)
            (source / 'note.txt').write_text('Substantive research evidence', encoding='utf-8')
            store = Mock()
            store.get.return_value = {'ids': []}
            documents = [Document(page_content='research text', metadata={})]
            with patch.object(ingest_domains, 'BASE_DIR', base), patch.object(ingest_domains, 'get_vector_store', return_value=store), patch.object(ingest_domains, 'prepare_documents', return_value=(documents, '')):
                ingest_domains.ingest_domain('clinical')
                first = store.add_documents.call_args.kwargs['ids']
                store.get.return_value = {'ids': first}
                ingest_domains.ingest_domain('clinical')
            self.assertEqual(store.add_documents.call_count, 1)


if __name__ == '__main__':
    unittest.main()
