"""Scores describe text similarity and source-domain coverage, not business ROI."""
import math
import re

DEFAULT_WEIGHTS = {'requirement_match': 0.7, 'domain_coverage': 0.3}


def cosine(a, b):
    if not a or len(a) != len(b) or any(not math.isfinite(v) for v in [*a, *b]):
        raise ValueError('Embedding vectors must be finite and have matching nonzero dimensions.')
    divisor = math.sqrt(sum(v*v for v in a) * sum(v*v for v in b))
    return max(0.0, min(1.0, sum(x*y for x, y in zip(a, b))/divisor)) if divisor else 0.0


def rank_candidates(question, candidates, registry, domains, embeddings, weights=None,
                    mandatory_constraints=(), verified_checks=None):
    weights = DEFAULT_WEIGHTS if weights is None else weights
    if (not weights or set(weights)-set(DEFAULT_WEIGHTS)
            or any(not math.isfinite(v) or v < 0 for v in weights.values()) or sum(weights.values()) <= 0):
        raise ValueError('Weights must be finite, nonnegative, supported and have a positive sum.')
    verified_checks = verified_checks or {}
    ranked, held, rejected = [], [], []
    seen = set()
    for candidate in candidates:
        identity = str(candidate.get('id', ''))
        refs = candidate.get('source_ids', [])
        required_fields = ('title', 'rationale', 'owner', 'success_metric', 'expected_impact')
        if (not identity or identity in seen or not isinstance(refs, list) or not refs or
                not set(refs) <= set(registry) or any(not isinstance(candidate.get(f), str) or not candidate[f].strip() for f in required_fields)):
            rejected.append(dict(id=identity, reason='Missing action fields, duplicate ID or invalid source references.'))
            continue
        seen.add(identity)
        item = {k: candidate.get(k) for k in ('id', 'title', 'rationale', 'kind', 'source_ids', 'owner',
                'prerequisites', 'success_metric', 'expected_impact', 'limitations')}
        # The LLM is not allowed to self-certify mandatory constraints.
        required = set(mandatory_constraints)
        purchase_language = re.search(r'\b(buy|purchase|procure|order|replace)\b', item['title'], re.I)
        if item.get('kind') == 'procurement' or purchase_language:
            item['kind'] = 'procurement'
            required.update(('compatibility', 'regulatory'))
        elif item.get('kind') != 'action':
            rejected.append(dict(id=identity, reason='Unknown proposal kind.'))
            continue
        checks = verified_checks.get(identity, {})
        unresolved = [name for name in sorted(required) if checks.get(name) != 'verified']
        if unresolved:
            held.append(dict(**item, score=None, unresolved_constraints=unresolved,
                             reason='Mandatory checks must be verified before this proposal can be ranked.'))
            continue
        ranked.append(item)
    if ranked:
        target = embeddings.embed_query(question)
        vectors = embeddings.embed_documents([c['title']+' '+c['rationale'] for c in ranked])
        if len(vectors) != len(ranked):
            raise ValueError('Embedding count did not match the number of proposals.')
        for candidate, vector in zip(ranked, vectors):
            covered = {ref.split(':')[0] for ref in candidate['source_ids']}
            factors = dict(requirement_match=cosine(target, vector),
                           domain_coverage=len(covered & set(domains))/max(1, len(set(domains))))
            candidate['factors'] = factors
            candidate['score'] = sum(weights[k]*factors[k] for k in weights)/sum(weights.values())
            candidate['explanation'] = 'Text similarity to customer requirements and fraction of requested domains cited; not a feasibility, compatibility or ROI estimate.'
        ranked.sort(key=lambda c: (-c['score'], c['id']))
    return dict(ranked=ranked, held=held, rejected=rejected, weights=weights,
                limitations=['Source-label validation does not establish claim entailment.',
                             'Cost, reliability and ROI are unknown unless separately verified.',
                             'Verified constraint checks are operator assertions in this prototype, not authentication.'])
