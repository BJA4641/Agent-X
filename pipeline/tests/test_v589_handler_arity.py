"""v5.8.9 — guard the handler signature contract.

The v5.8.8 deploy failed at runtime with
    TypeError: probe() takes 2 positional arguments but 3 were given
because new department handlers were written as (w, job) while the worker
calls every handler as (w, job, ctx). Compile-time checks cannot catch this,
so assert the arity of every registered handler here.
"""
import inspect, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_new_department_handlers_accept_ctx():
    from workers.departments import providers, strategy
    for mod, names in ((providers, ["probe"]), (strategy, ["arena_scout", "audit"])):
        for n in names:
            fn = getattr(mod, n)
            params = list(inspect.signature(fn).parameters)
            assert len(params) == 3, f"{mod.__name__}.{n} takes {params}, expected (w, job, ctx)"
            assert params[2] == "ctx", f"{mod.__name__}.{n} third arg is {params[2]!r}, expected 'ctx'"

def test_all_registered_handlers_have_matching_arity():
    """Every handler any department registers must take exactly 3 positional args."""
    from workers import departments
    seen = {}
    class FakeWorker:
        def register(self, job_type, handler): seen[job_type] = handler
    departments.register_all(FakeWorker())
    assert seen, "no handlers registered"
    bad = []
    for job_type, fn in seen.items():
        params = [p for p, s in inspect.signature(fn).parameters.items()
                  if s.kind in (s.POSITIONAL_ONLY, s.POSITIONAL_OR_KEYWORD)]
        if len(params) != 3:
            bad.append((job_type, params))
    assert not bad, f"handlers with wrong arity: {bad}"
