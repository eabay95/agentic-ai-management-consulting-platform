import argparse
import json
from config import ROOT
from agents.manager import route
from rag.retriever import retrieve


def cases():
    return json.loads((ROOT/'evaluation'/'consulting_questions.json').read_text('utf-8'))


def save(name,result):
    (ROOT/'artifacts').mkdir(exist_ok=True)
    (ROOT/'artifacts'/name).write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def evaluate_routing():
    rows=[]
    tp=fp=fn=0
    for case in cases():
        predicted=set(route(case['question']))
        expected=set(case['routes'])
        tp+=len(predicted&expected)
        fp+=len(predicted-expected)
        fn+=len(expected-predicted)
        rows.append(dict(question=case['question'],expected=sorted(expected),predicted=sorted(predicted),exact=predicted==expected))
    return save('routing_results.json',dict(exact_match_accuracy=sum(r['exact'] for r in rows)/len(rows),
              micro_precision=tp/(tp+fp) if tp+fp else 0,micro_recall=tp/(tp+fn) if tp+fn else 0,
              micro_f1=2*tp/(2*tp+fp+fn) if tp else 0,cases=rows,
              limitation='Small developer-labeled topic suite; not an independent benchmark.'))


def evaluate_retrieval(store,k=5):
    rows=[]
    for case in cases():
        if not case.get('sources') or not case.get('domain'):
            continue
        evidence=retrieve(store,case['domain'],case['question'],'public',k)
        names={e['metadata']['document_name'] for e in evidence}
        expected=set(case['sources'])
        rows.append(dict(question=case['question'],expected=sorted(expected),retrieved=sorted(names),
                         source_recall=len(names&expected)/len(expected)))
    return save('retrieval_results.json',dict(k=k,backend=store.embeddings.signature,
            mean_source_recall_at_k=sum(r['source_recall'] for r in rows)/len(rows) if rows else None,
            cases=rows,scope='Document-level labels, not passage relevance judgments; K per requested year.',
            human_quality_review='not_run'))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--retrieval',action='store_true')
    args=parser.parse_args()
    print(json.dumps(evaluate_routing(),indent=2))
    if args.retrieval:
        from rag.vector_store import VectorStore
        print(json.dumps(evaluate_retrieval(VectorStore()),indent=2))
