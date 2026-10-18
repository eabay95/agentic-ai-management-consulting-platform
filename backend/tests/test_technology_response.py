import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from rag.pipeline import graph
from rag.response_text import response_text
from langchain_core.documents import Document


class TechnologyResponseTests(unittest.TestCase):
    def test_model_text_blocks_are_normalized(self):
        self.assertEqual(response_text([{'type':'text','text':'RAG retrieves evidence.'},
                                        {'type':'thinking','text':'private reasoning'},
                                        {'type':'text','text':{'value':'Then generates an answer.'}}]),
                         'RAG retrieves evidence.\nThen generates an answer.')
        for value in (None, 12, {'unexpected':'value'}):
            self.assertEqual(response_text(value), '')

    def test_empty_collection_skips_gemini(self):
        store, model = Mock(), Mock()
        store.similarity_search.return_value = []
        result = graph.invoke(dict(question='what is RAG',domain='technology',vector_store=store,chat_model=model))
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertIsInstance(result['answer'], str)
        self.assertEqual(result['context'], [])
        model.invoke.assert_not_called()

    def test_populated_collection_returns_plain_text(self):
        store, model = Mock(), Mock()
        store.similarity_search.return_value = [Document(page_content='RAG retrieves documents before generation.')]
        model.invoke.return_value = SimpleNamespace(content=[{'type':'text','text':'RAG uses retrieved documents [T1].'}])
        result = graph.invoke(dict(question='what is RAG',domain='technology',vector_store=store,chat_model=model))
        self.assertEqual(result['answer'], 'RAG uses retrieved documents [T1].')
        self.assertEqual(result['status'], 'completed')

    def test_fabricated_citation_rejected(self):
        store, model = Mock(), Mock()
        store.similarity_search.return_value = [Document(page_content='RAG evidence.')]
        model.invoke.return_value = SimpleNamespace(content='An unsupported citation [T999].')
        with self.assertRaisesRegex(ValueError, 'unretrieved source'):
            graph.invoke(dict(question='what is RAG',domain='technology',vector_store=store,chat_model=model))

    def test_public_fetch_only_accepts_professor_references(self):
        from fetch_technology import fetch, PageText
        with self.assertRaisesRegex(ValueError, 'professor-listed'):
            fetch('https://example.com/not-listed')
        parser = PageText()
        parser.feed('<main>Actual source text<script>not evidence</script></main>')
        self.assertEqual(parser.parts, ['Actual source text'])

    def test_browser_renderer_accepts_text_blocks(self):
        html = (Path(__file__).resolve().parents[1] / 'web' / 'index.html').read_text('utf-8')
        helpers = html[html.index('function inline('):html.index("form.addEventListener('submit'")]
        script = '''const assert=require('node:assert/strict');
const document={createTextNode:text=>({textContent:text})};
function element(tag,text,className){return {tagName:tag.toUpperCase(),textContent:text||'',children:[],append(...items){this.children.push(...items);}};}
const names={technology:'Technology'};
''' + helpers + '''
const answer=[{type:'text',text:'RAG uses evidence [T1].'},{type:'thinking',text:'hidden'}];
assert.equal(answerText(answer),'RAG uses evidence [T1].');
for(const value of [answer,null,42,{unexpected:true},'A normal answer'])formattedAnswer(value);
const box=element('article');
render({agent_results:{technology:{status:'completed',answer,sources:[{id:'T1',document:'rag.txt',source_url:'https://cloud.google.com/example',excerpt:'Evidence'}]}}},box);
assert.ok(JSON.stringify(box).includes('RAG uses evidence'));
assert.ok(!JSON.stringify(box).includes('hidden'));
assert.ok(JSON.stringify(box).includes('Open source'));
'''
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
