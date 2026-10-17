def recommend(cart, rules, k=5):
    """Prefer full-cart rules; otherwise use satisfied subsets, labeled explicitly.

    Rank by antecedent coverage, confidence, lift, support; retain the best
    supporting rule for each product. These are associations, not causal effects.
    """
    cart = frozenset(cart)
    if not cart or rules.empty:
        return []
    matching = [r for r in rules.to_dict('records') if r['antecedents'] <= cart
                and r['consequents'] - cart]
    full = [r for r in matching if r['antecedents'] == cart]
    matching = full or matching
    candidates = {}
    for rule in matching:
        coverage = len(rule['antecedents']) / len(cart)
        score = (coverage, rule['confidence'], rule['lift'], rule['support'])
        for product in sorted(rule['consequents'] - cart):
            if product not in candidates or score > candidates[product]['rank']:
                candidates[product] = dict(product=product, rank=score,
                    antecedents=sorted(rule['antecedents']), coverage=coverage,
                    support=float(rule['support']), confidence=float(rule['confidence']),
                    lift=float(rule['lift']), fallback=not bool(full))
    return sorted(candidates.values(), key=lambda r: (tuple(-v for v in r['rank']), r['product']))[:k]
