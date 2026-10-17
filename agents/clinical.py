from .base import Specialist


class ClinicalAgent(Specialist):
    domain = 'clinical'
    scope = 'Analyze research, laboratory instruments and workflows. Separate clinical studies from Agilent instrument specifications.'
    missing = 'Provide assay, sample types, required throughput, accuracy, regulatory requirements and budget for instrument selection.'
