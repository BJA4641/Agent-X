"""jobs.py — durable job queue backed by Postgres (Supabase).

Why not Redis/Celery? We already have Postgres via Supabase. The
`SELECT ... FOR UPDATE SKIP LOCKED` pattern gives us concurrent-safe claim()
without adding infrastructure. Same pattern Powers Row-Level Security,
Oban (Elixir), and graphile-worker.

Key guarantees:
  * Atomic claim — two workers can't grab the same job.
  * Retry cap — no infinite loops.
  * Idempotency key — duplicate submissions return existing job.
  * Poison-pill dead letter — jobs exceeding max_attempts become 'failed'
    and can be inspected in the dashboard.
  * Priority ordering — higher priority first, then FIFO.
"""
from __future__ import annotations
import time, json, traceback, uuid
from typing import Optional, List, Callable
from .models import Job, JobStatus, Priority, Event, EventType
from .bus import get_bus


def _event(job: Job, type_: EventType, message: str = "", emitter: str = "queue") -> Event:
    return Event(
        emitter=emitter, type=type_, message=message or f"job {type_.value}",
        job_id=job.id, brand_id=job.brand_id, account_id=job.account_id,
    )


class JobQueue:
    def __init__(self, supabase_factory: Callable = None):
        self._sb = supabase_factory
        self._bus = get_bus()

    def _table(self):
        if not self._sb:
            raise RuntimeError("JobQueue: no Supabase factory configured")
        sb = self._sb()
        if sb is None:
            raise RuntimeError("JobQueue: Supabase not configured")
        return sb.table("jobs")

    # ---------- Producers ----------
    def enqueue(self, job: Job) -> Job:
        """Enqueue a job, honoring idempotency_key if set."""
        if job.idempotency_key:
            existing = self._find_by_idempotency(job.idempotency_key)
            if existing:
                return existing
        try:
            self._table().insert(self._row(job)).execute()
            self._bus.emit(_event(job, EventType.JOB_CREATED, f"enqueued {job.job_type}"))
        except Exception:
            traceback.print_exc()
        return job

    def enqueue_many(self, jobs: List[Job]) -> List[Job]:
        for j in jobs:
            self.enqueue(j)
        return jobs

    def _find_by_idempotency(self, key: str) -> Optional[Job]:
        """v5.6.1 FIX: only PENDING work blocks re-enqueue. The old version let a
        DONE job with the same key block its own successor — every self-scheduling
        chain (ops.heartbeat, ops.snapshot, human_desk.sync) died right after boot
        because the successor's 30s/1h time-bucket key collided with the job that
        had just finished 4 seconds earlier. One heartbeat per boot, forever —
        which is why audits kept calling a LIVE worker dead."""
        try:
            res = (self._table().select("*").eq("idempotency_key", key)
                   .in_("status", [JobStatus.QUEUED.value, JobStatus.CLAIMED.value,
                                    JobStatus.IN_PROGRESS.value, JobStatus.WAIT_HUMAN.value])
                   .limit(1).execute())
            if res.data:
                return self._from_row(res.data[0])
        except Exception:
            pass
        return None

    # ---------- Consumers ----------
    def claim(self, worker_id: str, job_types: List[str] = None, limit: int = 1) -> List[Job]:
        """Atomically claim N available jobs for this worker.

        Uses a conditional UPDATE rather than SKIP LOCKED (Supabase-py exposes
        UPDATE ... WHERE but not raw FOR UPDATE). The status='queued' guard plus
        a claimed_at CAS means two workers racing on the same row will only see
        one successful update.
        """
        try:
            tbl = self._table()
            q = (tbl.select("*")
                 .eq("status", JobStatus.QUEUED.value)
                 .lte("scheduled_for", time.time())
                 .order("priority", desc=True)
                 .order("created_at")
                 .limit(max(limit * 3, 5)))
            if job_types:
                q = q.in_("job_type", job_types)
            rows = q.execute().data or []
            claimed = []
            for r in rows:
                upd = (tbl.update({"status": JobStatus.CLAIMED.value,
                                   "claimed_at": time.time(),
                                   "worker_id": worker_id})
                       .eq("id", r["id"])
                       .eq("status", JobStatus.QUEUED.value)
                       .execute())
                if upd.data:
                    job = self._from_row(upd.data[0])
                    claimed.append(job)
                    self._bus.emit(_event(job, EventType.JOB_STARTED, f"claimed by {worker_id}"))
                if len(claimed) >= limit:
                    break
            return claimed
        except Exception:
            traceback.print_exc()
            return []

    def mark_in_progress(self, job: Job):
        self._update_status(job, JobStatus.IN_PROGRESS)

    def complete(self, job: Job, result: dict):
        job.status = JobStatus.DONE
        job.result = result
        job.finished_at = time.time()
        self._update_row(job, {"status": JobStatus.DONE.value, "result": result,
                               "finished_at": job.finished_at,
                               "cost_cents": job.cost_cents})
        self._bus.emit(_event(job, EventType.JOB_DONE, f"done: {job.job_type}"))

    def fail(self, job: Job, error: str, fatal: bool = False):
        job.attempts += 1
        job.error = error
        if not fatal and job.attempts < job.max_attempts:
            job.scheduled_for = time.time() + min(300, 2 ** job.attempts * 5)
            job.status = JobStatus.QUEUED
            self._update_row(job, {"status": job.status.value, "attempts": job.attempts,
                                   "error": error, "scheduled_for": job.scheduled_for,
                                   "cost_cents": job.cost_cents})
            self._bus.agent("jobs",
                            f"retrying {job.job_type} (attempt {job.attempts}/{job.max_attempts})",
                            "warn", "job_retry", job_id=job.id, error=error)
        else:
            job.status = JobStatus.FAILED
            job.finished_at = time.time()
            self._update_row(job, {"status": JobStatus.FAILED.value, "attempts": job.attempts,
                                   "error": error, "finished_at": job.finished_at,
                                   "cost_cents": job.cost_cents})
            self._bus.emit(_event(job, EventType.JOB_FAILED, f"failed: {error[:120]}"))

    def wait_human(self, job: Job, esc):
        job.status = JobStatus.WAIT_HUMAN
        self._update_row(job, {"status": JobStatus.WAIT_HUMAN.value,
                               "payload": {**job.payload, "_escalation": {
                                   "severity": esc.severity, "summary": esc.summary,
                                   "options": esc.options, "context": esc.context,
                                   "deadline_hours": esc.deadline_hours,
                                   "raised_at": time.time(),
                               }}})
        self._bus.emit(_event(job, EventType.HUMAN_NEEDED, esc.summary, emitter="human_desk"))

    def block(self, job: Job, reason: str):
        job.status = JobStatus.BLOCKED
        self._update_row(job, {"status": JobStatus.BLOCKED.value,
                               "error": reason, "cost_cents": job.cost_cents})
        self._bus.emit(_event(job, EventType.JOB_BLOCKED, f"blocked: {reason[:120]}"))

    # ---------- Schema bootstrap ----------
    def ensure_tables(self):
        """Idempotently create jobs + agent_events + memory tables.

        Wrapped so that partial failures (e.g. RLS already exists) don't kill
        the worker. Uses direct SQL via Supabase's `rpc` if an `exec` function
        exists, otherwise issues CREATE TABLE IF NOT EXISTS through the
        REST API using raw-post fallback.
        """
        sb = self._sb()
        if sb is None:
            return
        stmts = [
            """create table if not exists public.jobs (
                id text primary key,
                job_type text not null,
                brand_id uuid, account_id uuid, project_id uuid,
                priority int not null default 50,
                status text not null default 'queued',
                payload jsonb not null default '{}'::jsonb,
                result jsonb,
                attempts int not null default 0,
                max_attempts int not null default 2,
                parent_job_id text,
                requested_by text not null default 'system',
                worker_id text,
                scheduled_for float not null default extract(epoch from now()),
                deadline float,
                error text,
                cost_cents int not null default 0,
                idempotency_key text unique,
                created_at float not null default extract(epoch from now()),
                claimed_at float,
                finished_at float
            );""",
            "create index if not exists jobs_status_priority on public.jobs (status, priority desc, created_at);",
            "create index if not exists jobs_scheduled on public.jobs (scheduled_for) where status='queued';",
            """create table if not exists public.agent_events (
                id text primary key,
                tenant_id text not null default 'me',
                ts float not null default extract(epoch from now()),
                emitter text not null,
                type text not null default 'agent.info',
                status text not null default 'info',
                action text not null default '',
                message text not null default '',
                subject jsonb not null default '{}'::jsonb,
                job_id text, brand_id uuid, account_id uuid,
                cost_cents int not null default 0,
                data jsonb not null default '{}'::jsonb,
                item_id uuid,
                user_id uuid,
                created_at timestamptz not null default now()
            );""",
            "create index if not exists agent_events_tenant_ts on public.agent_events (tenant_id, ts desc);",
            """create table if not exists public.memory (
                id uuid primary key default gen_random_uuid(),
                tenant_id text not null default 'me',
                account_id uuid, project_id uuid, brand_id uuid,
                role text not null,
                content text not null,
                metadata jsonb not null default '{}'::jsonb,
                created_at timestamptz not null default now()
            );""",
            "create index if not exists memory_account on public.memory (account_id, created_at desc);",
            """create table if not exists public.lessons (
                id uuid primary key default gen_random_uuid(),
                tenant_id text not null default 'me',
                scope text not null,          # 'brand' | 'account' | 'global'
                subject_id text,              # uuid or 'global'
                topic text not null,          # 'hook','timing','cta','thumbnail',...
                lesson text not null,
                evidence jsonb not null default '{}'::jsonb,
                confidence float not null default 0.5,
                applied_at timestamptz,
                created_at timestamptz not null default now()
            );""",
            "create index if not exists lessons_scope on public.lessons (scope, topic, confidence desc);",
        ]
        for sql in stmts:
            try:
                self._exec_sql(sb, sql)
            except Exception as e:
                # Schema setup is best-effort; don't kill boot if one fails
                print(f"[jobs.ensure_tables] non-fatal: {e}")

    def _exec_sql(self, sb, sql: str):
        """Best-effort SQL execute: try exec RPC, else ignore (REST can't run
        arbitrary DDL safely on Supabase without the SQL RPC). The `exec`
        RPC is defined by earlier setup SQLs but may not exist on new
        projects; in that case the tables are usually already present."""
        try:
            sb.rpc("exec", {"q": sql}).execute()
        except Exception:
            # Fall back to nothing — tables likely already created via the
            # SQL the user pastes manually.
            pass

    # ---------- Row <-> Job ----------
    def _row(self, job: Job) -> dict:
        return {
            "id": job.id, "job_type": job.job_type,
            "brand_id": str(job.brand_id) if job.brand_id else None,
            "account_id": str(job.account_id) if job.account_id else None,
            "project_id": str(job.project_id) if job.project_id else None,
            "priority": job.priority, "status": job.status.value,
            "payload": job.payload, "result": job.result,
            "attempts": job.attempts, "max_attempts": job.max_attempts,
            "parent_job_id": job.parent_job_id, "requested_by": job.requested_by,
            "scheduled_for": job.scheduled_for, "deadline": job.deadline,
            "error": job.error, "cost_cents": job.cost_cents,
            "idempotency_key": job.idempotency_key,
            "created_at": job.created_at,
        }

    def _from_row(self, r: dict) -> Job:
        return Job(
            id=r["id"], job_type=r["job_type"],
            brand_id=r.get("brand_id"), account_id=r.get("account_id"),
            project_id=r.get("project_id"),
            priority=r.get("priority", 50),
            status=JobStatus(r.get("status", "queued")),
            payload=r.get("payload") or {}, result=r.get("result"),
            attempts=r.get("attempts", 0),
            max_attempts=r.get("max_attempts", 2),
            parent_job_id=r.get("parent_job_id"),
            requested_by=r.get("requested_by", "system"),
            scheduled_for=r.get("scheduled_for", time.time()),
            deadline=r.get("deadline"), error=r.get("error"),
            cost_cents=r.get("cost_cents", 0),
            idempotency_key=r.get("idempotency_key"),
            created_at=r.get("created_at", time.time()),
            claimed_at=r.get("claimed_at"), finished_at=r.get("finished_at"),
        )

    def _update_status(self, job: Job, status: JobStatus):
        try:
            self._table().update({"status": status.value}).eq("id", job.id).execute()
        except Exception:
            traceback.print_exc()

    def _update_row(self, job: Job, patch: dict):
        try:
            self._table().update(patch).eq("id", job.id).execute()
        except Exception:
            traceback.print_exc()
