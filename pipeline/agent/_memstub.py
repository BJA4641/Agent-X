"""_memstub.py — no-op memory stub used when real memory module fails to import.
Prevents stale Docker layers from crashing the container on boot.
"""

class MemoryStub:
    @staticmethod
    def add(**kw):
        pass

    @staticmethod
    def recent(**kw):
        return []

    @staticmethod
    def context_block(**kw):
        return "No prior guidance yet."

    @staticmethod
    def load_grade_feedback(**kw):
        return ""


def stub():
    return MemoryStub()
