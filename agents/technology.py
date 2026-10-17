from .base import Specialist


class TechnologyAgent(Specialist):
    domain = 'technology'
    scope = 'Analyze networking/cloud reliability, diagnostics, components and operational impact. Require exact hardware and software versions before compatibility claims.'
    missing = 'Provide device model, software version, symptoms, logs, topology and availability requirements before selecting replacements.'
