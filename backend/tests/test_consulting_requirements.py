import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agents.cross import CrossAgent
from rag.citations import check_citations
from rag.retrieval import retrieve_documents
from recommendations.ranker import rank_candidates
from recommendations.planner import RecommendationPlanner


def findings():
    return {domain:dict(status='completed',answer='Supported finding.',sources=[dict(id=label,source=f'{domain}.pdf',page=2,excerpt='Documented supporting evidence.')])
            for domain,label in [('technology','T1'),('sec','S1')]}


class CrossAgentTests(unittest.TestCase):
    def test_synthesis_connects_two_domains_and_preserves_source_ids(self):
        client=Mock()
        client.models.generate_content.return_value.text='Pilot the infrastructure [technology:T1] while monitoring supplier risk [sec:S1].'
        result=CrossAgent(client).run('Evaluate infrastructure and supplier financial risks',findings())
        self.assertEqual(result['status'],'generated_needs_review')
        self.assertTrue(result['citation_check']['valid'])
        self.assertEqual({s['id'] for s in result['sources']},{'technology:T1','sec:S1'})
        payload=json.loads(client.models.generate_content.call_args.kwargs['contents'])
        self.assertEqual(set(payload['specialist_findings']),{'technology','sec'})

    def test_invalid_or_absent_citations_are_withheld(self):
        for answer in ('Claim [technology:T999].','No references.','Claim [technology:T1, sec:S999].'):
            client=Mock(); client.models.generate_content.return_value.text=answer
            result=CrossAgent(client).run('Cross-domain decision',findings())
            self.assertEqual(result['status'],'citation_error')
            self.assertNotEqual(result['answer'],answer)

    def test_missing_specialist_does_not_call_model(self):
        client=Mock(); values=findings(); values['sec'].update(status='insufficient_evidence',sources=[])
        result=CrossAgent(client).run('Cross-domain decision',values)
        self.assertEqual(result['status'],'insufficient_evidence')
        client.models.generate_content.assert_not_called()

    def test_grouped_citations_checked(self):
        sources=[dict(id='S1'),dict(id='S2')]
        self.assertTrue(check_citations('Claim [S1, S2]',sources)['valid'])
        self.assertFalse(check_citations('Claim [S1, S999]',sources)['valid'])

    def test_error_and_uncited_findings_are_excluded(self):
        for status in ('error','citation_error','uncited_needs_review'):
            values=findings();values['sec']['status']=status
            self.assertFalse(CrossAgent(client=Mock()).has_usable_answer(values['sec']))


class Embeddings:
    def embed_query(self,text): return [1.0,0.0]
    def embed_documents(self,texts): return [[1.0,0.0] if 'power' in text else [.8,.6] for text in texts]


def candidate(identity='power',kind='action',sources=None):
    return dict(id=identity,kind=kind,title=identity,rationale='Documented rationale',source_ids=sources or ['technology:T1'],
                owner='Network team',success_metric='Observed outage duration',expected_impact='Expected reduction in outages',
                prerequisites=['Confirm requirements'],limitations=['Pilot required'])


class RecommendationTests(unittest.TestCase):
    def setUp(self): self.registry={'technology:T1':{},'sec:S1':{}}
    def test_ranking_uses_requirements_and_configurable_weights(self):
        a=candidate();b=candidate('alternative',sources=['technology:T1','sec:S1'])
        first=rank_candidates('requirements',[a,b],self.registry,['technology','sec'],Embeddings(),{'requirement_match':1.0})
        self.assertEqual(first['ranked'][0]['id'],'power')
        second=rank_candidates('requirements',[a,b],self.registry,['technology','sec'],Embeddings(),{'domain_coverage':1.0})
        self.assertEqual(second['ranked'][0]['id'],'alternative')
        self.assertNotIn('cost',first['ranked'][0]['factors'])

    def test_unknown_and_failed_mandatory_checks_hold_purchase(self):
        for checks in ({},{'power':{'compatibility':'failed','regulatory':'verified'}}):
            result=rank_candidates('router',[candidate(kind='procurement')],self.registry,['technology'],Embeddings(),verified_checks=checks)
            self.assertEqual(result['ranked'],[])
            self.assertIsNone(result['held'][0]['score'])

    def test_purchase_mislabeled_as_action_still_requires_checks(self):
        proposal=candidate();proposal['title']='Buy replacement router'
        result=rank_candidates('router',[proposal],self.registry,['technology'],Embeddings())
        self.assertEqual(result['ranked'],[])
        self.assertEqual(result['held'][0]['kind'],'procurement')

    def test_verified_checks_allow_ranking(self):
        result=rank_candidates('router',[candidate(kind='procurement')],self.registry,['technology'],Embeddings(),
            verified_checks={'power':{'compatibility':'verified','regulatory':'verified'}})
        self.assertEqual(len(result['ranked']),1)

    def test_custom_constraint_is_hard_not_score_penalty(self):
        result=rank_candidates('router',[candidate()],self.registry,['technology'],Embeddings(),mandatory_constraints=['budget_approval'])
        self.assertEqual(result['ranked'],[])
        self.assertEqual(result['held'][0]['unresolved_constraints'],['budget_approval'])

    def test_bad_sources_and_incomplete_actions_rejected(self):
        invalid=candidate(sources=['fake:Q1']); incomplete=candidate('missing');incomplete.pop('owner')
        result=rank_candidates('router',[invalid,incomplete],self.registry,['technology'],Embeddings())
        self.assertEqual(len(result['rejected']),2)

    def test_invalid_weights_rejected(self):
        for weights in ({},{'cost':1},{'requirement_match':-1},{'requirement_match':float('nan')},{'requirement_match':0}):
            with self.assertRaises(ValueError):
                rank_candidates('router',[],self.registry,['technology'],Embeddings(),weights)

    def test_planner_integrates_valid_candidates(self):
        client=Mock(); client.models.generate_content.return_value.text=json.dumps({'candidates':[candidate()]})
        result=RecommendationPlanner(client,Embeddings()).run('Which power checks should we perform?',findings())
        self.assertEqual(result['status'],'ranked_proposals')
        self.assertEqual(result['ranked'][0]['owner'],'Network team')


class RetrievalGuardTests(unittest.TestCase):
    def test_missing_company_year_does_not_retrieve_other_filing(self):
        store=Mock(); store.get.return_value={'metadatas':[dict(company='Agilent',reporting_period='2025-10-31')]}
        self.assertEqual(retrieve_documents(store,'sec','Cisco fiscal 2025 risks'),[])
        store.similarity_search.assert_not_called()

    def test_company_year_filter(self):
        store=Mock(); store.get.return_value={'metadatas':[dict(company='Cisco',reporting_period='2025-07-26')]}
        retrieve_documents(store,'sec','Cisco 2025 risks')
        filters=store.similarity_search.call_args.kwargs['filter']['$and']
        self.assertIn({'reporting_period':{'$in':['2025-07-26']}},filters)

    def test_cisco_and_agilent_queries_stay_in_sources(self):
        for domain,question,organization in [('technology','Cisco router','Cisco'),('clinical','Agilent throughput','Agilent')]:
            store=Mock();retrieve_documents(store,domain,question)
            self.assertIn(organization,str(store.similarity_search.call_args.kwargs['filter']))


class ConsultationIntegrationTests(unittest.TestCase):
    def test_multi_agent_endpoint_synthesizes_and_ranks(self):
        with patch('agents.manager.get_gemini_client',return_value=Mock()):
            import main
        routing=dict(domains=['technology','sec'],requires_cross_domain_reasoning=True,status='routed')
        cross=Mock();cross.run.return_value=dict(status='generated_needs_review',answer='Integrated',sources=[])
        planner=Mock();planner.run.return_value=dict(status='ranked_proposals',ranked=[])
        with patch.object(main.manager,'route',return_value=routing),patch.object(main,'run_specialist',side_effect=lambda d,*args:findings()[d]),patch.object(main,'get_cross_agent',return_value=cross),patch.object(main,'get_recommendation_planner',return_value=planner):
            result=main.consult(main.CSRQuestionRequest(question='Should we invest in Cisco infrastructure?'))
        self.assertEqual(result['status'],'completed')
        cross.run.assert_called_once();planner.run.assert_called_once()

    def test_invalid_synthesis_makes_consultation_partial(self):
        with patch('agents.manager.get_gemini_client',return_value=Mock()):
            import main
        cross=Mock();cross.run.return_value=dict(status='citation_error',answer='Withheld')
        with patch.object(main.manager,'route',return_value=dict(domains=['technology','sec'],requires_cross_domain_reasoning=True)),patch.object(main,'run_specialist',side_effect=lambda d,*args:findings()[d]),patch.object(main,'get_cross_agent',return_value=cross):
            result=main.consult(main.CSRQuestionRequest(question='Compare technology and finance findings'))
        self.assertEqual(result['status'],'partial')


class QualityEvaluationTests(unittest.TestCase):
    def test_model_rubric_is_validated_and_labeled(self):
        from evaluation.judge import evaluate_answer, CRITERIA
        client=Mock()
        rating={key:dict(score=4,rationale='Supported by cited excerpt; completeness needs review.') for key in CRITERIA}
        rating['source_ids']=['technology:T1']
        client.models.generate_content.return_value.text=json.dumps(rating)
        row=dict(question='Which action?',result={'agent_results':findings()})
        response=evaluate_answer(client,row,'test-model')
        self.assertEqual(response['status'],'model_judged_needs_human_review')
        rating['groundedness']['score']=99
        client.models.generate_content.return_value.text=json.dumps(rating)
        with self.assertRaises(ValueError):evaluate_answer(client,row,'test-model')

    def test_no_answer_has_no_invented_quality_score(self):
        from evaluation.judge import evaluate_answer
        client=Mock()
        response=evaluate_answer(client,dict(question='Missing',result={}), 'test-model')
        self.assertEqual(response['status'],'not_run')
        client.models.generate_content.assert_not_called()


class EvaluationApiTests(unittest.TestCase):
    def test_saved_report_and_page_are_available(self):
        from fastapi.testclient import TestClient
        with patch('agents.manager.get_gemini_client',return_value=Mock()):
            import main
        client=TestClient(main.app)
        self.assertEqual(client.get('/evaluation/view').status_code,200)
        report=client.get('/evaluation')
        self.assertEqual(report.status_code,200)
        self.assertIn('retrieval',report.json())

    def test_routing_quota_is_explained(self):
        from fastapi import HTTPException
        with patch('agents.manager.get_gemini_client',return_value=Mock()):
            import main
        class QuotaError(Exception):code=429
        with patch.object(main.manager,'route',side_effect=QuotaError()):
            with self.assertRaises(HTTPException) as caught:
                main.consult(main.CSRQuestionRequest(question='What is MCP?'))
        self.assertEqual(caught.exception.status_code,429)
        self.assertIn('quota',caught.exception.detail)
