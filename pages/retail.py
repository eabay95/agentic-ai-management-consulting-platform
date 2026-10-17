import streamlit as st
from recommendations.market_basket import recommend
from ui import retail_model,parameters

st.title('Retail Market Basket')
st.write('Explore the professor’s electronic-retail catalog and discover products purchased together.')
try:
    baskets,_,rules = retail_model(**parameters())
except Exception as error:
    st.error(f'Could not load or mine the provided retail data: {error}')
    st.stop()
catalog = sorted(set().union(*baskets))
cart = st.session_state.setdefault('cart',[])
left,right = st.columns([1.2,1])
with left:
    st.subheader('Product catalog')
    search = st.text_input('Search product name or SKU')
    available = [p for p in catalog if search.lower() in p.lower() and p not in cart]
    if available:
        selected = st.selectbox('Select product',available)
        if st.button('Add Item',type='primary'):
            cart.append(selected)
            st.rerun()
    else:
        st.info('No additional products match your search.')
    st.caption(f'{len(catalog)} actual products · {len(baskets):,} historical transactions')
with right:
    st.subheader(f'Current shopping cart · {len(cart)}')
    if not cart:
        st.info('Your cart is empty. Add a product to see relevant associations.')
    for index,product in enumerate(cart):
        st.write(product)
        if st.button('Remove Item',key='remove_'+str(index)):
            cart.remove(product)
            st.rerun()
    if st.button('Clear Cart',disabled=not cart):
        cart.clear()
        st.rerun()
st.divider()
st.subheader('Recommended Products')
results = recommend(cart,rules)
if not results:
    st.info('No recommendations: no qualifying association rule matches the current cart.' if cart else 'Recommendations appear after you add an item.')
for index,result in enumerate(results):
    with st.container(border=True):
        st.write('**'+result['product']+'**')
        st.caption(('Subset fallback — ' if result['fallback'] else 'Full-cart match — ')+', '.join(result['antecedents']))
        st.write(f"Support {result['support']:.1%} · Confidence {result['confidence']:.1%} · Lift {result['lift']:.2f} · Cart coverage {result['coverage']:.0%}")
        if st.button('Add recommended product',key='rec_'+str(index)):
            cart.append(result['product'])
            st.rerun()
st.caption('Recommendations reflect purchase associations, not hardware compatibility or causation. Ranked by cart coverage, confidence, lift and support.')
