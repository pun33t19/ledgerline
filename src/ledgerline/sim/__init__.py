"""The attack simulator behind the Lab UI.

Each scenario runs twice at the same time: **unprotected** (agent talks
straight to a malicious demo server) and **protected** (the same agent talks
through the real Ledgerline proxy). Everything that happens is reported as a
stream of typed events (:mod:`.events`), which the UI animates and the tests
assert on.
"""
