# Patch notes for pipeline/agent/__init__.py
#
# You don't need to replace __init__.py (you don't have one — it's imported
# implicitly as a namespace package). But IF you add an __init__.py for
# explicit exports, include these:
#
#   from . import brand, qa, planner, connections
#   __all__ = ["brand", "qa", "planner", "connections"]
#
# No other init changes needed.
