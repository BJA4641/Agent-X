"""worker.py — generic worker loop.

One worker pulls from the JobQueue, dispatches to the right handler, handles
retries, cost tracking, and escalation. This replaces the monolithic
`orchestrator.tick()` with a proper worker pool.
"""
from __future__ import annotations
import os, threading, time, traceback, uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Callable, Optional
from .models import Job, JobStatus, HumanEscalation, AgentContext
from .jobs import JobQueue
from .bus import get_bus
from .observability import Tracer, Span


Handler = Callable[["Worker", Job, AgentContext], None]


# v5.10.2 REQ-LANES-1 (DEC-030): jobs are not interchangeable. A 400-token LLM
# call is network-bound and safe to run many-at-once; a video render is memory-
# bound and will OOM a 512 MB container if run wide. Lanes give each class its
# own concurrency budget so heavy work can never starve — or crash — light work.
HEAVY_JOB_PREFIXES = ("creative.render", "creative.write_carousel", "postprod.")
FREE_ONLY_JOB_PREFIXES = ("paused.",)


def lane_for(job_type: str) -> str:
    jt = job_type or ""
    if jt.startswith(FREE_ONLY_JOB_PREFIXES):
        return "free_only"
    if jt.startswith(HEAVY_JOB_PREFIXES):
        return "heavy"
    return "light"


class Worker:
    def __init__(self, queue: JobQueue, name: str = None, poll_interval: float = 3.0):
        self.id = (name or f"worker-{uuid.uuid4().hex[:6]}")
        self.queue = queue
        self.bus = get_bus()
        self.tracer = Tracer()
        self.handlers: Dict[str, Handler] = {}
        self.poll_interval = poll_interval
        # v5.6 circuit breaker: N identical consecutive failures on a job_type
        # pauses that job_type for BREAKER_HOLD_S instead of retrying forever.
        # (v5.5.1 failed creative.write_script 7,220 times in a row.)
        self._fail_streaks: Dict[str, dict] = {}
        self._breaker_until: Dict[str, float] = {}
        self.BREAKER_THRESHOLD = 5
        self.BREAKER_HOLD_S = 1800
        self._running = False
        self._ctx = AgentContext(run_id=uuid.uuid4().hex[:12], deps={})
        # v5.10.2 REQ-PARALLEL-1 (DEC-029). Execution was strictly sequential
        # (claim limit=1), so 105 accounts shared ONE execution slot and the
        # daily SLA was unreachable by construction. Work here is network-bound,
        # so threads give near-linear throughput inside the same 512 MB
        # container — no new infrastructure, no extra spend.
        # Rollback: WORKER_CONCURRENCY=1 restores v5.10.1 behaviour exactly.
        self.concurrency = max(1, int(os.environ.get("WORKER_CONCURRENCY", "4")))
        self._lane_caps = {
            "light": max(1, int(os.environ.get("LANE_LIGHT", "4"))),
            "heavy": max(1, int(os.environ.get("LANE_HEAVY", "1"))),
            "free_only": max(1, int(os.environ.get("LANE_FREE_ONLY", "2"))),
        }
        self._lane_sems = {k: threading.Semaphore(v) for k, v in self._lane_caps.items()}
        self._state_lock = threading.Lock()
        self._last_beat = 0.0
        self._started_at = time.time()

    def register(self, job_type: str, handler: Handler):
        self.handlers[job_type] = handler

    def set_deps(self, **deps):
        self._ctx.deps.update(deps)

    def run_forever(self):
        self._running = True
        self.bus.agent(self.id, f"worker {self.id} started — types: {list(self.handlers.keys())}", "success", "worker_up")
        while self._running:
            # v5.11.10 REQ-HEALTH-3 — heartbeat from the LOOP, not only a thread.
            #
            # Liveness has been signalled two ways, and both can fail silently:
            # an ops.heartbeat JOB (dies when the queue stalls) and a daemon
            # PULSE thread (v5.9.6). On 2026-07-24 the worker wrote a provider
            # report at 02:12 while worker_health had been frozen since 01:46 and
            # settings.heartbeat_pulse was NULL — the thread was not running at
            # all, so a working worker showed a 29-minute-dead banner.
            #
            # The claim loop is the one thing that MUST execute for the worker to
            # be doing anything. Beating from here makes the signal structural:
            # if this line stops running, the worker really has stopped.
            self._beat()
            try:
                jobs = self.queue.claim(self.id, job_types=list(self.handlers.keys()),
                                        limit=self.concurrency)
                if not jobs:
                    time.sleep(self.poll_interval)
                    continue
                if self.concurrency == 1 or len(jobs) == 1:
                    self._execute(jobs[0])
                else:
                    self._execute_batch(jobs)
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.bus.agent(self.id, f"worker loop error: {e}", "error", "worker_error")
                traceback.print_exc()
                time.sleep(self.poll_interval)

    def _beat(self, min_interval_s: float = 15.0):
        """Write worker_health straight from the claim loop. Rate-limited, and
        failure here must never interrupt work."""
        now = time.time()
        if now - getattr(self, "_last_beat", 0) < min_interval_s:
            return
        self._last_beat = now
        try:
            factory = self.deps.get("supabase") if hasattr(self, "deps") else None
            factory = factory or (self._ctx.deps.get("supabase") if self._ctx else None)
            sb = factory() if callable(factory) else None
            if sb is None:
                return
            from workers.departments.ops import _write_health_row, VERSION_HINT
            _write_health_row(sb, self.id, getattr(self, "_started_at", now),
                              VERSION_HINT())
        except Exception:
            pass

    def _execute_batch(self, jobs):
        """Run a claimed batch across the thread pool, respecting lane caps."""
        def _run(job):
            lane = lane_for(job.job_type)
            sem = self._lane_sems.get(lane) or self._lane_sems["light"]
            with sem:
                try:
                    self._execute(job)
                except Exception as e:
                    self.bus.agent(self.id, f"job {job.job_type} crashed in pool: {e}",
                                   "error", "pool_error")
                    traceback.print_exc()

        with ThreadPoolExecutor(max_workers=self.concurrency,
                                thread_name_prefix="agentx") as pool:
            list(pool.map(_run, jobs))

    def stop(self):
        self._running = False

    # ---------- Execution ----------
    def _execute(self, job: Job):
        ctx = self._ctx.child(job_id=job.id, brand_id=job.brand_id,
                              account_id=job.account_id, project_id=job.project_id,
                              priority=job.priority)
        # v5.6 circuit breaker: if this job_type is tripped, park the job.
        with self._state_lock:
            until = self._breaker_until.get(job.job_type, 0)
        if until > time.time():
            try:
                self.queue._update_row(job, {"status": "queued",
                                              "scheduled_for": until,
                                              "error": "circuit breaker open"})
            except Exception:
                pass
            return
        try:
            self.queue.mark_in_progress(job)
            handler = self.handlers.get(job.job_type)
            if not handler:
                self.queue.fail(job, f"no handler for job type {job.job_type}", fatal=True)
                return
            with self.tracer.span(job.job_type, agent=job.job_type.split(".")[0]) as span:
                span.annotate("job_id", job.id)
                span.annotate("brand_id", job.brand_id)
                handler(self, job, ctx)
                span.annotate("cost_cents", job.cost_cents)
            # If handler didn't fail and didn't wait_human, complete
            self._fail_streaks.pop(job.job_type, None)
            if job.status == JobStatus.IN_PROGRESS:
                self.queue.complete(job, job.result or {"ok": True})
                try:
                    from workers.departments.ops import _bump_counters
                    _bump_counters(True)
                except Exception:
                    pass
        except HumanEscalation as esc:
            self.queue.wait_human(job, esc)
            try:
                from workers.departments.ops import _bump_counters
                _bump_counters(False)
            except Exception:
                pass
        except Exception as e:
            tb = traceback.format_exc()
            self.bus.agent(job.job_type.split(".")[0], f"error: {str(e)[:200]}", "error",
                           "job_error", job_id=job.id)
            print(tb)
            self.queue.fail(job, f"{type(e).__name__}: {e}",
                            fatal=type(e).__name__ == "FatalError")
            self._record_failure(job, f"{type(e).__name__}: {e}")
            try:
                from workers.departments.ops import _bump_counters
                _bump_counters(False)
            except Exception:
                pass

    # ---------- Helpers for handlers ----------
    def spawn(self, job_type: str, payload: dict, **kwargs) -> Job:
        """Spawn a follow-up job (next step in a workflow)."""
        j = Job(job_type=job_type, payload=payload,
                brand_id=kwargs.get("brand_id"),
                account_id=kwargs.get("account_id"),
                project_id=kwargs.get("project_id"),
                priority=kwargs.get("priority", 50),
                parent_job_id=kwargs.get("parent_job_id"),
                max_attempts=kwargs.get("max_attempts", 2),
                idempotency_key=kwargs.get("idempotency_key"))
        self.queue.enqueue(j)
        self.bus.agent(self.id, f"spawned {job_type} → job {j.id[:8]}", "info", "job_spawn", job_id=j.id)
        return j

    def fail_job(self, job: Job, reason: str, fatal: bool = False):
        self.queue.fail(job, reason, fatal=fatal)
        self._record_failure(job, reason)

    def _record_failure(self, job: Job, reason: str):
        """v5.6: track consecutive identical failures per job_type; trip the
        breaker at threshold so one broken step can't loop thousands of times."""
        sig = (reason or "?")[:120]
        st = self._fail_streaks.get(job.job_type)
        if st and st.get("sig") == sig:
            st["n"] += 1
        else:
            st = {"sig": sig, "n": 1}
            self._fail_streaks[job.job_type] = st
        if st["n"] >= self.BREAKER_THRESHOLD and self._breaker_until.get(job.job_type, 0) < time.time():
            self._breaker_until[job.job_type] = time.time() + self.BREAKER_HOLD_S
            self.bus.agent("ops",
                f"⛔ CIRCUIT BREAKER: {job.job_type} failed {st['n']}x in a row with the same "
                f"error — pausing this job type for {self.BREAKER_HOLD_S//60} min. Error: {sig}",
                "critical", "circuit_breaker", job_id=job.id)
            sb_f = self._ctx.deps.get("supabase")
            if sb_f:
                try:
                    import datetime as _dt
                    sb_f().table("ceo_recommendations").insert({
                        "severity": "critical", "category": "ops",
                        "recommendation": f"⛔ {job.job_type} is broken — circuit breaker engaged",
                        "reasoning": f"{st['n']} consecutive identical failures: {sig}. The job type is "
                                     f"paused for {self.BREAKER_HOLD_S//60} minutes. Deploy a fix; the "
                                     f"breaker resets automatically after the hold.",
                        "projected_roi": 0.0, "projected_value_usd": 0.0,
                        "action_url": "/dashboard/agents",
                        "day": _dt.date.today().isoformat(),
                    }).execute()
                except Exception:
                    pass
