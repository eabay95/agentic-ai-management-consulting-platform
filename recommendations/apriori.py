"""Real transaction parsing and mlxtend Apriori; never fits on held-out baskets."""
from pathlib import Path
import zipfile
import pandas as pd
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori, association_rules


def load_baskets(path):
    path = Path(path)
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.lower().endswith('.csv')]
            if len(names) != 1:
                raise ValueError('Retail archive must contain exactly one CSV.')
            with archive.open(names[0]) as source:
                frame = pd.read_csv(source, dtype='string')
    else:
        frame = pd.read_csv(path, dtype='string')
    expected = ['transaction_id', *[f'item_{i}' for i in range(1, 6)]]
    if frame.columns.tolist() != expected:
        raise ValueError(f'Expected {expected}; received {frame.columns.tolist()}')
    if frame.transaction_id.isna().any() or frame.transaction_id.str.strip().eq('').any():
        raise ValueError('Missing transaction IDs cannot preserve basket boundaries.')
    frame['transaction_id'] = frame.transaction_id.str.strip()
    long = frame.melt(id_vars='transaction_id', value_vars=expected[1:], value_name='product')
    long['product'] = long['product'].str.strip()
    long = long.dropna(subset=['product'])
    long = long.loc[long['product'].ne('')].drop_duplicates(['transaction_id', 'product'])
    return [frozenset(values) for values in long.groupby('transaction_id', sort=False)['product'].agg(list)]


def mine(baskets, support=0.005, confidence=0.08, lift=1.0, max_len=3):
    if not 0 < support <= 1 or not 0 <= confidence <= 1 or lift < 0:
        raise ValueError('Invalid support, confidence or lift threshold.')
    if not baskets:
        return pd.DataFrame(columns=['support', 'itemsets']), pd.DataFrame()
    encoder = TransactionEncoder()
    encoded = encoder.fit_transform([sorted(b) for b in baskets])
    matrix = pd.DataFrame(encoded, columns=encoder.columns_, dtype=bool)
    itemsets = apriori(matrix, min_support=support, use_colnames=True, max_len=max_len)
    if itemsets.empty or not itemsets.itemsets.map(len).gt(1).any():
        return itemsets, pd.DataFrame()
    rules = association_rules(itemsets, metric='confidence', min_threshold=confidence,
                              num_itemsets=len(baskets))
    rules = rules.loc[rules.lift.ge(lift)].reset_index(drop=True)
    return itemsets, rules
