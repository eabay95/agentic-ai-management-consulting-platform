import streamlit as st
from recommendations.metrics import evaluate
from ui import retail_model,parameters

st.title('Apriori Analytics')
params = parameters()
try:
    baskets,itemsets,rules = retail_model(**params)
except Exception as error:
    st.error(str(error))
    st.stop()
for column,label,value in zip(st.columns(4),['Transactions','Products','Frequent itemsets','Useful rules'],
                              [len(baskets),len(set().union(*baskets)),len(itemsets),len(rules)]):
    column.metric(label,value)
st.write('Support is the fraction of baskets containing an itemset. Confidence is how often a consequent appears when its antecedent appears. Lift compares that confidence with the consequent’s overall frequency. These measures do not establish causation.')
display = itemsets.copy()
display['itemsets'] = display.itemsets.map(lambda items:', '.join(sorted(items)))
st.subheader('Frequent itemsets')
st.dataframe(display.sort_values('support',ascending=False),width='stretch')
st.bar_chart(display.nlargest(12,'support').set_index('itemsets')['support'])
st.subheader('Association rules')
if rules.empty:
    st.info('No association rules meet these thresholds.')
else:
    show = rules[['antecedents','consequents','support','confidence','lift']].copy()
    for col in ['antecedents','consequents']:
        show[col] = show[col].map(lambda items:', '.join(sorted(items)))
    st.dataframe(show.sort_values(['confidence','lift'],ascending=False),width='stretch')
    st.scatter_chart(show,x='support',y='confidence',size='lift')
    st.download_button('Download rules CSV',show.to_csv(index=False),'association_rules.csv')
st.subheader('Held-out recommendation evaluation')
st.caption('Rules above use all data for the demonstration. Evaluation retrains from an independent 80% training split, grouping duplicate baskets, and hides half of each test basket.')
if st.button('Run real-data evaluation'):
    with st.spinner('Mining training baskets only…'):
        st.json(evaluate(baskets,**params))
