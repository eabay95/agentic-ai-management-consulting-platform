from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_all_pages_render():
    app=AppTest.from_file('app.py',default_timeout=45).run()
    assert not app.exception
    for page in ['pages/retail.py','pages/apriori_analytics.py','pages/knowledge_base.py','pages/evaluation.py']:
        app.switch_page(page).run()
        assert not app.exception,[(e.message) for e in app.exception]


def test_cart_updates_and_removal():
    app=AppTest.from_file('app.py',default_timeout=45).run().switch_page('pages/retail.py').run()
    assert app.session_state['cart']==[]
    selected=app.selectbox[0].value
    next(b for b in app.button if b.label=='Add Item').click().run()
    assert app.session_state['cart']==[selected]
    assert selected not in app.selectbox[0].options
    assert any(b.label=='Add recommended product' for b in app.button)
    next(b for b in app.button if b.label=='Add recommended product').click().run()
    assert len(app.session_state['cart'])==2
    next(b for b in app.button if b.label=='Remove Item').click().run()
    assert len(app.session_state['cart'])==1
    next(b for b in app.button if b.label=='Clear Cart').click().run()
    assert app.session_state['cart']==[]
