import json
import unittest
from unittest.mock import Mock, patch

from agents.manager import ManagerAgent
from agents.routing_policy import apply_domain_policy
from rag.retrieval import retrieve_documents

QUESTION = ('According to the uploaded clinical research, how is machine learning used '
            'to predict heart attacks, and what limitations are reported?')


def classifier_response(domains):
    return json.dumps(dict(domains=domains,confidence={d:.9 for d in domains},
                           reasons={d:'Model classification' for d in domains},missing_information=[]))


class ClinicalRoutingTests(unittest.TestCase):
    def manager(self, domains):
        client=Mock()
        client.models.generate_content.return_value.text=classifier_response(domains)
        return ManagerAgent(client=client)

    def test_exact_reported_question_removes_spurious_technology_route(self):
        result=self.manager(['clinical','technology']).route(QUESTION)
        self.assertEqual(result['domains'],['clinical'])
        self.assertFalse(result['requires_cross_domain_reasoning'])
        self.assertEqual(set(result['reasons']),{'clinical'})
        self.assertEqual(set(result['confidence']),{'clinical'})
        self.assertTrue(result['routing_adjustments'])

    def test_clinical_is_added_if_classifier_selects_only_technology(self):
        result=self.manager(['technology']).route(QUESTION)
        self.assertEqual(result['domains'],['clinical'])
        self.assertNotIn('clinical',result['confidence'])  # No invented model score.

    def test_cloud_deployment_retains_both_specialists(self):
        result=self.manager(['clinical','technology']).route(
            'How should we deploy a heart attack prediction model on Google Cloud and evaluate its clinical limitations?')
        self.assertEqual(result['domains'],['clinical','technology'])
        self.assertTrue(result['requires_cross_domain_reasoning'])

    def test_explicit_finance_and_csr_routes_are_preserved(self):
        result=self.manager(['clinical','technology','sec','csr']).route(
            'Compare Agilent clinical assay needs, supplier financial risks and sustainability.')
        self.assertEqual(result['domains'],['clinical','sec','csr'])
        self.assertTrue(result['requires_cross_domain_reasoning'])

    def test_neural_network_research_is_not_enterprise_networking(self):
        domains,_=apply_domain_policy('What do clinical studies report about neural networks for heart disease?',
                                      ['clinical','technology'])
        self.assertEqual(domains,['clinical'])

    def test_direct_technology_retrieval_cannot_fall_back_to_cloud_documents(self):
        store=Mock()
        self.assertEqual(retrieve_documents(store,'technology',QUESTION),[])
        store.similarity_search.assert_not_called()

    def test_supplier_name_alone_does_not_add_clinical_to_finance(self):
        result=self.manager(['sec']).route('What financial risks does Agilent disclose in its 2025 SEC filing?')
        self.assertEqual(result['domains'],['sec'])

    def test_nonmedical_technology_questions_remain_technology(self):
        for question in ('What is MCP?', 'What is RAG?', 'How do Cisco routers work?'):
            self.assertEqual(self.manager(['technology']).route(question)['domains'],['technology'])

    def test_consultation_calls_only_clinical_for_reported_question(self):
        with patch('agents.manager.get_gemini_client',return_value=Mock()):
            import main
        clinical=dict(status='completed',domain='clinical',answer='Reported findings [C1].',
                      sources=[dict(id='C1',source='research.pdf',page=2,excerpt='Research findings.')])
        with patch.object(main,'manager',self.manager(['clinical','technology'])), \
             patch.object(main,'run_specialist',return_value=clinical) as specialist, \
             patch.object(main,'get_cross_agent') as cross:
            result=main.consult(main.CSRQuestionRequest(question=QUESTION))
        self.assertEqual(set(result['agent_results']),{'clinical'})
        specialist.assert_called_once_with('clinical',QUESTION,None)
        cross.assert_not_called()
