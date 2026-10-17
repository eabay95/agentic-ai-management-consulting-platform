import pytest
from agents.manager import route,ManagerAgent
from evaluation.evaluate_agents import cases
from customer.context import CustomerStore
from recommendations.consulting_ranker import rank


@pytest.mark.parametrize('case',cases())
def test_labeled_routes(case):
    assert set(route(case['question']))==set(case['routes'])


def test_follow_up():
    assert set(route('What about the next year?',[{'question':'Cisco SEC financial risks'}]))=={'sec'}


def test_customer_histories(tmp_path):
    store=CustomerStore(tmp_path)
    a=store.create('A'); b=store.create('B')
    store.append(a['id'],'Private question',{'summary':'Private answer'})
    assert len(store.get(a['id'])['history'])==1
    assert store.get(b['id'])['history']==[]
    with pytest.raises(ValueError):
        store.get('../public')


def test_hard_constraints_and_unknown_scores():
    candidates=[dict(title='unknown',constraints={},factors={'cost':1}),
                dict(title='allowed',constraints={'compatibility':True},factors={}),
                dict(title='blocked',constraints={'compatibility':False},factors={'cost':1})]
    results=rank(candidates,required_constraints=['compatibility'])
    assert [r['title'] for r in results]==['allowed']
    assert results[0]['score'] is None


def test_shared_manager_no_retained_profile():
    class EmptyStore:
        def search(self,*args,**kwargs): return []
    manager=ManagerAgent(EmptyStore())
    a=manager.answer('Cisco router connectivity',{'id':'a','history':[]},False)
    b=manager.answer('food insecurity',{'id':'b','history':[]},False)
    assert set(a['routes'])=={'technology'}
    assert set(b['routes'])=={'csr'}
    assert a['specialists'][0]['status']=='insufficient_evidence'
    assert not hasattr(manager,'profile')
