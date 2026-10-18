import json
import tempfile
import unittest
from contextlib import nullcontext
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import fetch_technology as sources


class PublicSourceTests(unittest.TestCase):
    def test_agilent_is_clinical_even_when_reference_is_in_technology(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            folder=base/'data'/'technology'
            folder.mkdir(parents=True)
            (folder/'Agilent.txt').write_text('https://www.agilent.com/example')
            (folder/'Google GCP.txt').write_text('https://cloud.google.com/example')
            with patch.object(sources,'BASE_DIR',base):
                result=sources.reference_sources()
            self.assertEqual(result['https://www.agilent.com/example']['domain'],'clinical')
            self.assertEqual(result['https://cloud.google.com/example']['domain'],'technology')

    def test_successful_fetch_is_cached_with_source_url(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            folder=base/'data'/'technology'
            folder.mkdir(parents=True)
            url='https://cloud.google.com/example'
            (folder/'Google GCP.txt').write_text(url)
            headers=Message()
            headers['Content-Type']='text/html; charset=utf-8'
            body=('<main>Model Context Protocol enables tools and data access. '+('documented source text '*20)+'</main>').encode()
            response=SimpleNamespace(headers=headers,read=lambda limit:body)
            opener=Mock()
            opener.open.side_effect=lambda *args,**kwargs:nullcontext(response)
            with patch.object(sources,'BASE_DIR',base),patch.object(sources,'build_opener',return_value=opener):
                first=sources.fetch(url)
                second=sources.fetch(url)
                self.assertEqual(first,second)
                self.assertEqual(opener.open.call_count,1)
                self.assertIn('Model Context Protocol',first.read_text())
                self.assertEqual(json.loads(first.with_suffix('.source.json').read_text())['source_url'],url)
                sources.fetch(url,refresh=True)
                self.assertEqual(opener.open.call_count,2)

    def test_batch_records_failure_and_preserves_other_results(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            refs={'https://cloud.google.com/a':{'domain':'technology','reference_file':'Google GCP.txt'},
                  'https://www.agilent.com/b':{'domain':'clinical','reference_file':'Agilent.txt'}}
            def fetch(url,refresh=False):
                if 'agilent' in url: raise ValueError('403 access blocked')
                return base/'source.txt'
            with patch.object(sources,'BASE_DIR',base),patch.object(sources,'reference_sources',return_value=refs),patch.object(sources,'fetch',side_effect=fetch):
                report=sources.fetch_all()
            self.assertEqual([r['status'] for r in report],['available','unavailable'])
            saved=json.loads((base/'data'/'public_source_report.json').read_text())
            self.assertEqual(saved[1]['error'],'403 access blocked')
