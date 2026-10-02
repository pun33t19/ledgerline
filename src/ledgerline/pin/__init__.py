"""Tool-definition pinning: approve tool definitions once, then refuse any that change.

Defeats "rug pulls", where a server swaps a tool's description (or schema)
after it was approved. See ADR-004.
"""
