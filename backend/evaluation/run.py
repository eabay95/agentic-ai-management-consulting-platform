"""Run local retrieval/ranking and optionally paid live Gemini routing/answer checks."""
import argparse
import csv
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from rag.vector_store import get_vector_store
from rag.retrieval import retrieve_documents
from rag.citations import check_citations
from recommendations.ranker import rank_candidates
from llm import get_embeddings, get_model, LOCAL_EMBEDDING_MODEL

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE/name).read_text('utf-8-sig'))


def evaluate_routing(classifier, cases):
    rows, tp, fp, fn = [], 0, 0, 0
    quota_limited = False
    for case in cases:
        try:
            if quota_limited:
                raise RuntimeError('not_run_quota_exhausted')
            predicted = set(classifier.route(case['question'])['domains'])
            error = None
        except Exception as exc:
            predicted, error = set(), 'not_run_quota_exhausted' if quota_limited else type(exc).__name__
            if getattr(exc, 'code', None) == 429:
                quota_limited = True
                error = 'HTTP_429_quota_exhausted'
        expected = set(case['domains'])
        tp += len(expected & predicted); fp += len(predicted - expected); fn += len(expected - predicted)
        rows.append(dict(id=case['id'], expected=sorted(expected), predicted=sorted(predicted),
                         exact=expected == predicted and not error, error=error))
        print('Routing evaluated:',case['id'],flush=True)
    successful = [r for r in rows if not r['error']]
    return dict(status='completed' if len(successful)==len(rows) else 'incomplete_api_errors', completed_cases=len(successful), total_cases=len(rows),
                exact_match_accuracy=sum(row['exact'] for row in successful)/len(successful) if len(successful)==len(rows) else None,
                exact_match_on_completed_cases=sum(row['exact'] for row in successful)/len(successful) if successful else None,
                micro_precision=(tp/(tp+fp) if tp+fp else 0) if len(successful)==len(rows) else None,
                micro_recall=(tp/(tp+fn) if tp+fn else 0) if len(successful)==len(rows) else None,
                micro_f1=(2*tp/(2*tp+fp+fn) if tp else 0) if len(successful)==len(rows) else None, cases=rows)


def evaluate_retrieval(k=5):
    stores, rows = {}, []
    for case in load('retrieval_cases.json'):
        domain = case['domain']
        if domain not in stores: stores[domain] = get_vector_store(domain)
        store = stores[domain]
        if domain == 'csr':
            documents = store.similarity_search(case['question'], k=k, filter={'report_year':case['year']})
        else:
            documents = retrieve_documents(store,domain,case['question'],k)
        names = {Path(d.metadata.get('source','').replace('\\','/')).name for d in documents}
        expected = set(case['sources'])
        returned_pages = {d.metadata.get('page_number',d.metadata.get('page',-1)+1)
                          for d in documents if Path(d.metadata.get('source','').replace('\\','/')).name in expected}
        page_recall = len(set(case['pages']) & returned_pages)/len(case['pages']) if case['pages'] else None
        rows.append(dict(id=case['id'],source_recall_at_k=len(names & expected)/len(expected),
                         labeled_page_recall_at_k=page_recall,
                         retrieved=[dict(source=d.metadata.get('source'),page=d.metadata.get('page_number',d.metadata.get('page',-1)+1)) for d in documents]))
    pages = [r['labeled_page_recall_at_k'] for r in rows if r['labeled_page_recall_at_k'] is not None]
    return dict(k=k,mean_source_recall_at_k=sum(r['source_recall_at_k'] for r in rows)/len(rows),
                mean_labeled_page_recall_at_k=sum(pages)/len(pages),cases=rows,
                limitation='Small developer-labeled source/page set, not exhaustive passage relevance labels.')


def evaluate_ranking():
    registry = {'technology:T1':dict(excerpt='Cisco 8300 dual power supplies for redundancy.'),
                'technology:T2':dict(excerpt='Google MCP connects models to tools.')}
    candidates = [dict(id='power',kind='action',title='Verify Catalyst 8300 dual power supply resilience',
                       rationale='Inspect and test redundant power supplies before a pilot.',source_ids=['technology:T1'],
                       owner='Network operator',success_metric='Observed failover duration',expected_impact='Expected reduction in unplanned outages'),
                  dict(id='mcp',kind='action',title='Review Google Cloud Model Context Protocol tool access',
                       rationale='Assess model connections to external tools and data.',source_ids=['technology:T2'],
                       owner='Cloud architect',success_metric='Tool-call success rate',expected_impact='Expected improvement in tool integration')]
    labels = [('Cisco Catalyst 8300 power supply redundancy and failover','power'),
              ('Google Cloud MCP model context protocol tools integration','mcp')]
    rows = []
    for query, relevant in labels:
        result = rank_candidates(query,candidates,registry,['technology'],get_embeddings())
        ranking = [c['id'] for c in result['ranked']]
        rows.append(dict(query=query,expected_first=relevant,ranked_ids=ranking,
                         precision_at_1=float(ranking[0] == relevant),reciprocal_rank=1/(ranking.index(relevant)+1)))
    return dict(precision_at_1=sum(r['precision_at_1'] for r in rows)/len(rows),
                mean_reciprocal_rank=sum(r['reciprocal_rank'] for r in rows)/len(rows),cases=rows,
                limitation='Two labeled fixed-candidate scenarios test semantic ranking, not live recommendation business value.')


def live_answers():
    import main
    questions = [
        'What is Model Context Protocol (MCP) according to the Google Cloud documentation?',
        'For a food-security nonprofit, should we pilot Cisco Catalyst 8300 networking considering documented power-supply resilience, Cisco fiscal 2025 financial risks, and SOFI 2024 food access priorities?'
    ]
    rows = []
    for index, question in enumerate(questions):
        print('Live answer evaluation:',index+1,flush=True)
        try:
            result = main.consult(main.CSRQuestionRequest(question=question))
            checks = {}
            for domain, response in result.get('agent_results',{}).items():
                checks[domain] = check_citations(response.get('answer',''),response.get('sources',[]))
            rows.append(dict(question=question,domains=result.get('domains'),status=result['status'],
                             citation_identity_checks=checks,
                             synthesis_citations=(result.get('synthesis') or {}).get('citation_check'),
                             recommendation_fields_complete=all(all(c.get(f) for f in ('owner','success_metric','expected_impact')) for c in (result.get('recommendations') or {}).get('ranked',[]))
                                  if (result.get('recommendations') or {}).get('ranked') else None,
                             result=result))
        except Exception as exc:
            rows.append(dict(question=question,error=type(exc).__name__))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--tests',action='store_true')
    args = parser.parse_args()
    report = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),model=get_model(),embedding_model=LOCAL_EMBEDDING_MODEL,
                  retrieval=evaluate_retrieval(),recommendation_ranking=evaluate_ranking())
    if args.live:
        from agents.manager import ManagerAgent
        report['routing'] = evaluate_routing(ManagerAgent(),load('routing_cases.json'))
        report['live_answers'] = live_answers()
    else:
        report['routing'] = dict(status='not_run',reason='Use --live to call Gemini.')
    if args.tests:
        completed = subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-v'],capture_output=True,text=True)
        report['regression_tests'] = dict(exit_code=completed.returncode,output=completed.stderr)
    report['human_quality_review'] = dict(status='pending',metrics=['factual groundedness','recommendation relevance','completeness','clarity'],
          rubric='Score 1-5 per answer, cite supporting source pages, record reviewer and rationale. Do not treat structural checks as response-quality ratings.')
    report['limitations'] = ['Small developer-authored suites are not independent held-out benchmarks.',
                            'Model confidence is not calibrated accuracy. Citation identity is not claim entailment.',
                            'Unknown costs, clinical outcomes and equipment compatibility remain unknown.']
    (HERE/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with (HERE/'human_review.csv').open('w',newline='',encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['question','reviewer','groundedness_1_to_5','relevance_1_to_5','completeness_1_to_5','clarity_1_to_5','source_ids_and_rationale'])
        for row in report.get('live_answers',[]): writer.writerow([row['question'],'','','','','',''])
    print('Saved evaluation/results.json and evaluation/human_review.csv',flush=True)


if __name__ == '__main__':
    main()
