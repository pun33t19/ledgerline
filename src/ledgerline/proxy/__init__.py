"""The Ledgerline proxy: sits between an MCP client and server and inspects every message.

The transports (:mod:`.stdio`, :mod:`.http`) move bytes; :mod:`.interceptor`
defines the hooks where checks plug in (tool pinning now; ledger, policy and
approvals in later phases).
"""
