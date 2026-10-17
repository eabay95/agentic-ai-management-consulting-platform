import pandas as pd
import pytest
from config import RESOURCES
from recommendations.apriori import load_baskets,mine
from recommendations.market_basket import recommend
from recommendations.metrics import evaluate


def test_real_data():
    baskets=load_baskets(RESOURCES/'Retail.zip')
    assert len(baskets)==1000
    assert len(set().union(*baskets))==40
    itemsets,rules=mine(baskets)
    assert not itemsets.empty and not rules.empty
    assert all(0 < value <= 1 for value in rules.support)
    cart=next(iter(baskets))
    assert not {r['product'] for r in recommend(cart,rules)} & cart


def test_exact_fallback_and_empty():
    rules=pd.DataFrame([
        dict(antecedents=frozenset('AB'),consequents=frozenset('C'),support=.3,confidence=.8,lift=1.6),
        dict(antecedents=frozenset('A'),consequents=frozenset('D'),support=.2,confidence=.7,lift=1.4)])
    assert recommend([],rules)==[]
    assert recommend(['Z'],rules)==[]
    assert recommend(['A','B'],rules)[0]['product']=='C'
    assert not recommend(['A','B'],rules)[0]['fallback']
    assert recommend(['A','Z'],rules)[0]['fallback']
    assert recommend(['A','B','C','D'],rules)==[]


def test_transaction_boundaries(tmp_path):
    path=tmp_path/'data.csv'
    pd.DataFrame([['1','A','A','',' ',None],['1','B',None,None,None,None],['2','C',None,None,None,None],
                  ['3',None,None,None,None,None]],columns=['transaction_id',*[f'item_{i}' for i in range(1,6)]]).to_csv(path,index=False)
    assert load_baskets(path)==[frozenset(['A','B']),frozenset(['C'])]


def test_apriori_fixture_metrics():
    baskets=[frozenset('AB'),frozenset('AB'),frozenset('AC'),frozenset('A')]
    _,rules=mine(baskets,.25,.4,0)
    result=next(r for r in rules.to_dict('records') if r['antecedents']==frozenset('A') and r['consequents']==frozenset('B'))
    assert result['support']==.5 and result['confidence']==.5
    assert result['lift']==1


def test_evaluation_reproducible():
    baskets=load_baskets(RESOURCES/'Retail.zip')
    first=evaluate(baskets)
    assert first==evaluate(baskets)
    assert first['train_transactions']+first['test_transactions']==1000
    assert 0 <= first['precision_at_k'] <= 1
