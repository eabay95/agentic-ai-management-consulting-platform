DEFAULT_WEIGHTS = {'relevance': 0.3, 'reliability': 0.2, 'cost': 0.15,
                   'business_impact': 0.2, 'operational_risk': 0.15}


def rank(candidates, weights=None, required_constraints=()):
    """Unknown mandatory constraints exclude a candidate. Unknown scores stay unknown.

    All supplied factors use 0..1 desirability (higher means better), including
    cost and risk. Scores are comparable only with identical factor availability.
    """
    weights = DEFAULT_WEIGHTS if weights is None else weights
    if not weights or any(v < 0 for v in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError('Ranking weights must be nonnegative with a positive total.')
    output = []
    for candidate in candidates:
        if any(candidate.get('constraints', {}).get(c) is not True for c in required_constraints):
            continue
        factors = candidate.get('factors', {})
        if any(not 0 <= value <= 1 for value in factors.values() if value is not None):
            raise ValueError('Factors must be in [0, 1].')
        available = {k:v for k,v in factors.items() if k in weights and v is not None and weights[k] > 0}
        score = (sum(weights[k]*v for k,v in available.items())/sum(weights[k] for k in available)) if available else None
        output.append({**candidate, 'score': score, 'known_factors': sorted(available),
                       'missing_factors': sorted(set(weights)-set(available))})
    return sorted(output, key=lambda c: (tuple(c['known_factors']), -(c['score'] if c['score'] is not None else -1)))
