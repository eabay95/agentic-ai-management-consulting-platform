import json
import unittest
from unittest.mock import Mock, patch

from agents.tasks import build_specialist_tasks
from agents.cross import CrossAgent

QUESTION = ('Our food-security nonprofit is considering Cisco Catalyst 8300 networking for field operations. '
            'What should we evaluate about its technical capabilities, Cisco financial risks disclosed in fiscal 2025, '
            'and food-access priorities identified in SOFI 2024? Recommend next steps and measurable success indicators.')


def results_with_scoped_limitations():
    return {
        'technology':dict(status='completed',answer='Catalyst 8300 supports SD-WAN [T1]. However, there is insufficient evidence about SEC and SOFI in these technical excerpts.',
                          sources=[dict(id='T1',document='Catalyst 8300 datasheet',page=3,excerpt='Documented SD-WAN capability.')]),
        'sec':dict(status='completed',answer='Disclosed supply-chain risks require due diligence [S1].',
                   sources=[dict(id='S1',document='Cisco 2025 filing',page=31,excerpt='Disclosed supply-chain risk.')]),
        'csr':dict(status='generated_needs_review',answer='Food affordability informs program priorities [S1].',
                   sources=[dict(id='S1',document='SOFI 2024',page=23,excerpt='Healthy diet affordability.')])}


class DomainTaskTests(unittest.TestCase):
    def test_queries_preserve_in_scope_entities_and_years(self):
        tasks=build_specialist_tasks(QUESTION,['technology','sec','csr'])
        self.assertIn('Catalyst 8300',tasks['technology'])
        self.assertNotIn('2025',tasks['technology'])
        self.assertNotIn('SOFI',tasks['technology'])
        self.assertIn('field operations',tasks['technology'])
        self.assertIn('environmental suitability',tasks['technology'])
        self.assertIn('Cisco',tasks['sec'])
        self.assertIn('2025',tasks['sec'])
        self.assertNotIn('2024',tasks['sec'])
        self.assertNotIn('Catalyst 8300',tasks['sec'])
        self.assertIn('SOFI 2024',tasks['csr'])
        self.assertNotIn('Cisco',tasks['csr'])
        self.assertNotIn('2025',tasks['csr'])

    def test_single_domain_question_is_preserved(self):
        question='According to clinical research, how does ML predict heart attacks?'
        self.assertEqual(build_specialist_tasks(question,['clinical']),{'clinical':question})

    def test_valid_technical_findings_survive_out_of_domain_caveat(self):
        client=Mock()
        client.models.generate_content.return_value.text=('Pilot documented networking [technology:T1], evaluate supplier risks '
                                                         '[sec:S1] and align with food priorities [csr:S1].')
        result=CrossAgent(client).run(QUESTION,results_with_scoped_limitations())
        self.assertEqual(result['status'],'generated_needs_review')
        self.assertEqual(set(result['used_domains']),{'technology','sec','csr'})
        self.assertEqual(result['skipped_domains'],{})
        payload=json.loads(client.models.generate_content.call_args.kwargs['contents'])
        self.assertIn('technology',payload['specialist_findings'])

    def test_synthesis_cannot_silently_omit_usable_technology_evidence(self):
        client=Mock();client.models.generate_content.return_value.text='Consider vendor risk [sec:S1] and food priorities [csr:S1].'
        result=CrossAgent(client).run(QUESTION,results_with_scoped_limitations())
        self.assertEqual(result['status'],'citation_error')
        self.assertEqual(result['citation_check']['missing_domains'],['technology'])
        self.assertNotIn('Consider vendor risk',result['answer'])

    def test_failed_technology_is_still_excluded(self):
        findings=results_with_scoped_limitations()
        findings['technology'].update(status='insufficient_evidence',answer='No usable technical evidence.',sources=[])
        prepared=CrossAgent(client=Mock()).prepare_evidence(findings)
        self.assertNotIn('technology',prepared['prepared'])
        self.assertIn('technology',prepared['skipped'])

    def test_api_dispatches_domain_subquestions_and_shows_them(self):
        with patch('agents.manager.get_gemini_client',return_value=Mock()):
            import main
        routing=dict(domains=['technology','sec','csr'],requires_cross_domain_reasoning=True)
        cross=Mock();cross.run.return_value=dict(status='generated_needs_review',answer='Integrated',sources=[])
        planner=Mock();planner.run.return_value=dict(status='ranked_proposals',ranked=[])
        with patch.object(main.manager,'route',return_value=routing), \
             patch.object(main,'run_specialist',side_effect=lambda d,*args:results_with_scoped_limitations()[d]) as specialist, \
             patch.object(main,'get_cross_agent',return_value=cross), \
             patch.object(main,'get_recommendation_planner',return_value=planner):
            result=main.consult(main.CSRQuestionRequest(question=QUESTION))
        self.assertEqual(result['status'],'completed')
        tasks=result['specialist_tasks']
        for call in specialist.call_args_list:
            domain,subquestion,_=call.args
            self.assertEqual(subquestion,tasks[domain])
            self.assertNotEqual(subquestion,QUESTION)
        self.assertEqual(cross.run.call_args.kwargs['question'],QUESTION)


class SourceScopeTests(unittest.TestCase):
    def test_item_1a_body_is_distinguished_from_toc(self):
        from langchain_core.documents import Document
        from rag.sec_sections import risk_factor_pages
        pages=[Document(page_content='Item 1A.\nRisk Factors ........ 11\nItem 1B.\nOther .... 20',metadata={'page':1}),
               Document(page_content='Item 1A.\nRisk Factors\nSupply chain disruptions.',metadata={'page':10}),
               Document(page_content='Competition risk.',metadata={'page':11}),
               Document(page_content='Item 1B.\nUnresolved Staff Comments',metadata={'page':12}),
               Document(page_content='Other content.',metadata={'page':13})]
        self.assertEqual(risk_factor_pages(pages),{10,11,12})

    def test_financial_risk_query_uses_risk_section_when_available(self):
        from rag.retrieval import retrieve_documents
        store=Mock();store.get.return_value={'metadatas':[dict(company='Cisco',reporting_period='2025-07-26',section='risk_factors')]}
        retrieve_documents(store,'sec','Cisco financial risks in fiscal 2025')
        self.assertIn({'section':{'$eq':'risk_factors'}},store.similarity_search.call_args.kwargs['filter']['$and'])

    def test_named_hardware_family_does_not_retrieve_another_router_family(self):
        from rag.retrieval import retrieve_documents
        store=Mock();retrieve_documents(store,'technology','Cisco Catalyst 8300 technical capabilities')
        self.assertIn({'product_family':{'$in':['catalyst 8300']}},store.similarity_search.call_args.kwargs['filter']['$and'])
