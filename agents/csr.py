from .base import Specialist


class CSRAgent(Specialist):
    domain = 'csr'
    scope = 'Analyze food security, malnutrition, conflict and prices; distinguish each report year. Propose measurable KPIs without invented baselines.'
    missing = 'Specify geography, population, report year, intervention budget and desired social outcomes.'
