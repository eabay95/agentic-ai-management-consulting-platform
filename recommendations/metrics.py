import random
from .apriori import mine
from .market_basket import recommend


def evaluate(baskets, k=5, seed=256, **parameters):
    if len(baskets) < 5:
        raise ValueError('At least five baskets required for evaluation.')
    # Identical baskets stay in the same split to avoid duplicate-basket leakage.
    unique = sorted(set(baskets), key=lambda b: tuple(sorted(b)))
    random.Random(seed).shuffle(unique)
    boundary = max(1, min(len(unique)-1, int(len(unique)*0.8)))
    train_keys = set(unique[:boundary])
    train = [b for b in baskets if b in train_keys]
    test = [b for b in baskets if b not in train_keys and len(b) >= 2]
    _, rules = mine(train, **parameters)
    precision, recall, covered, hit = [], [], 0, 0
    for basket in test:
        items = sorted(basket)
        rng = random.Random(str(seed)+'|'.join(items))
        rng.shuffle(items)
        split = max(1, len(items)//2)
        observed, target = set(items[:split]), set(items[split:])
        predicted = {r['product'] for r in recommend(observed, rules, k)}
        overlap = len(predicted & target)
        precision.append(overlap/k)  # strict Precision@K, empty slots count as misses
        recall.append(overlap/len(target))
        covered += bool(predicted)
        hit += bool(overlap)
    n = len(test)
    return dict(train_transactions=len(train), test_transactions=n, seed=seed, k=k,
                precision_at_k=sum(precision)/n if n else None,
                recall_at_k=sum(recall)/n if n else None,
                coverage=covered/n if n else None, hit_rate=hit/n if n else None,
                useful_rules=len(rules), parameters=parameters,
                protocol='80/20 unique-basket split; half-basket holdout; strict Precision@K')
