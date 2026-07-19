"""worker.py — generic worker loop.

One worker pulls from the JobQueue, dispatches to the right handler, handles
retries, cost tracking, and escalation. This replaces the monolithic
`orchestrator.tick()` with a proper worker pool.
"""
from __future__ import annotations
import time, traceback, uuid, threading
from typing import Dict, Callable, Optional
from .models import Job, JobStatus, HumanEscalation, AgentContext
from .jobs import JobQueue
from .bus import get_bus
from .observability import Tracer, Span


Handler = Callable[["Worker", Job, AgentContext], None]


class Worker:
    def __init__(self, queue: JobQueue, name: str = None, poll_interval: float = 3.0):
        self.id = (name or f"worker-{uuid.uuid4().hex[:6]}")
        self.queue = queue
        self.bus = get_bus()
        self.tracer = Tracer()
        self.handlers: Dict[str, Handler] = {}
        self.poll_interval = poll_interval
        self._running = False
        self._ctx = AgentContext(run_id=uuid.uuid4().hex[:12], deps={})

    def register(self, job_type: str, handler: Handler):
        self.handlers[job_type] = handler

    def set_deps(self, **deps):
        self._ctx.deps.update(deps)

    def run_forever(self):
        self._running = True
        self.bus.agent(self.id, f"worker {self.id} started — types: {list(self.handlers.keys())}", "success", "worker_up")
        while self._running:
            try:
                jobs = self.queue.claim(self.id, job_types=list(self.handlers.keys()), limit=1)
                if not jobs:
                    time.sleep(self.poll_interval)
                    continue
                job = jobs[0]
                self._execute(job)
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.bus.agent(self.id, f"worker loop error: {e}", "error", "worker_error")
                traceback.print_exc()
                time.sleep(self.poll_interval)

    def stop(self):
        self._running = False

    # ---------- Execution ----------
    def _execute(self, job: Job):
        ctx = self._ctx.child(job_id=job.id, brand_id=job.brand_id,
                              account_id=job.account_id, project_id=job.project_id,
                              priority=job.priority)
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
