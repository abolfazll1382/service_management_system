"""Demo data and the demo-reset feature.

This package is the one place in ``core`` that knows about every other app (it seeds users,
services, requests and the audit trail). Nothing imports it except ``config.urls`` and the
``seed_demo_data`` management command, so it adds no import cycle: think of it as a composition
root that happens to live next to the shared code.
"""
