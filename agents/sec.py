from .base import Specialist


class SECAgent(Specialist):
    domain = 'sec'
    scope = 'Analyze disclosed financial and operational risks. Preserve exact figure units, periods and company attribution; never imply live market data.'
    missing = 'Specify the company, fiscal year, decision horizon and risk tolerance.'
