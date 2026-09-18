"""THE TURN LOOP, TIMESTAMPED — where 728 seconds actually go.

Everything before this measured the wall and the turn COUNT. A count reports
activity and says nothing about whether any of it was the model working: 88
turns and 728s is consistent with 700s of generation, 700s of queueing, or 700s
of a container sitting idle on a socket, and those are three different fixes.

WHY THE STREAM ALONE IS NOT ENOUGH. `--output-format stream-json` emits ONE LINE
PER COMPLETE ASSISTANT MESSAGE. The line appears when generation has already
finished, so the interval before it collapses queue + prefill + generation into
one opaque number — precisely the split that decides whether this is a thinking
problem or a latency problem. `--include-partial-messages` adds the delta events
(`message_start`, `content_block_delta`, `message_stop`), and with those the
interval comes apart:

    previous event -> message_start        WAITING (queue + prefill; no tokens yet)
    message_start  -> first delta          TIME TO FIRST TOKEN
    first delta    -> message_stop         GENERATING (tokens on the wire)
    tool_use       -> tool_result          TOOL
    everything else                        NEITHER   <- the number nobody has

AND CPU SETTLES THE ARGUMENT. A gap with the container pinned is local work; a
gap with the container at zero is a wait on somebody else's machine, and "the
model is thinking" is not a thing that happens in this container at all. So a
sampler reads the cgroup's own CPU accounting alongside the clock. Absent that
file it says ABSENT rather than reporting a zero that would read as "idle".
"""
import json
import os
import threading
import time


def _cpu_usec():
    """(state, usec, throttled_usec) — CPU and THROTTLING for this container.

    Returns a STATE, never a bare number: a missing cgroup file and a genuinely
    idle container both produce 0, and those must not be the same reading.

    THROTTLING IS THE SECOND SUSPECT AND IT IS DIRECTLY OBSERVABLE. If the
    container's quota is below what the CLI wants, the kernel parks it at the
    end of every period and the wall stretches while nothing is wrong with the
    model, the tools or the prompt. `throttled_usec` is the kernel saying so in
    its own words, and it is the difference between "the agent is thinking" and
    "the agent is on the run queue".
    """
    try:
        d = {}
        with open("/sys/fs/cgroup/cpu.stat", encoding="utf-8") as fh:
            for ln in fh:
                k, _, v = ln.partition(" ")
                d[k.strip()] = int(v.strip() or 0)
        if "usage_usec" in d:
            return "MEASURED", d["usage_usec"], d.get("throttled_usec", 0)
    except Exception:                                             # noqa: BLE001
        pass
    try:
        with open("/sys/fs/cgroup/cpuacct/cpuacct.usage", encoding="utf-8") as fh:
            return "MEASURED", int(fh.read().strip()) // 1000, 0
    except Exception:                                             # noqa: BLE001
        pass
    return "ABSENT", 0, 0


def cpu_quota():
    """(state, cores) — what this container is ACTUALLY allowed, read in it.

    NOT the documented default. `edit` declares no `cpu=` at all while the
    principal declares cpu=8, so the allocation is whatever Modal gives an
    unspecified function — and a number quoted from documentation is an
    inference wearing a measurement's clothes. Ask the cgroup.
    """
    # cgroup v2, then v1, then the per-process cpuset — in that order, because
    # the first run read ABSENT and `os.cpu_count()` returned the HOST's 17,
    # which is the exact field this repo has already recorded publishing a
    # host number as a container's allocation.
    try:
        with open("/sys/fs/cgroup/cpu.max", encoding="utf-8") as fh:
            q, p = fh.read().split()
        return ("UNLIMITED", None) if q == "max" else \
               ("MEASURED", round(int(q) / int(p), 3))
    except Exception:                                             # noqa: BLE001
        pass
    try:
        with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", encoding="utf-8") as fh:
            q = int(fh.read().strip())
        with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us", encoding="utf-8") as fh:
            p = int(fh.read().strip())
        return ("UNLIMITED", None) if q <= 0 else ("MEASURED", round(q / p, 3))
    except Exception:                                             # noqa: BLE001
        pass
    try:
        # what the scheduler will actually let this process run on
        return "MEASURED_AFFINITY", len(os.sched_getaffinity(0))
    except Exception:                                             # noqa: BLE001
        return "ABSENT", None


def _mem_bytes():
    """(state, current_bytes) for THIS CONTAINER, from its own cgroup.

    NOT psutil and NOT os — the question is what the CONTAINER is using, and
    an observable must be computed on the side of the boundary it describes.
    cgroup v2 first, then v1, then ABSENT with the paths named: a memory
    figure that silently fell back to the host is the defect this lane has
    already paid for on cpu_count.
    """
    for _p in ("/sys/fs/cgroup/memory.current",
               "/sys/fs/cgroup/memory/memory.usage_in_bytes"):
        try:
            with open(_p, encoding="utf-8") as fh:
                return "MEASURED", int(fh.read().strip())
        except Exception:                                         # noqa: BLE001
            continue
    return "ABSENT", 0


class CpuSampler(threading.Thread):
    """Samples container CPU AND MEMORY so a gap can be attributed and the
    container can be SIZED.

    RSS WAS NOT SAMPLED AND THE CONTAINER IS SIZED BY GUESS BECAUSE OF IT.
    Measured on run-1789522875: 0.146 cores mean against 16.125 given — 0.9%
    — with zero throttling, because the container spends its wall WAITING on
    the model and on ChatCut. The CPU side of that was recorded; the memory
    side was not, so half the sizing question had no number at all.
    """

    def __init__(self, t0, every=0.25):
        super().__init__(daemon=True)
        self.t0, self.every, self.rows, self._stop = t0, every, [], False
        self.state, self._last, self._thr0 = _cpu_usec()
        self._lastthr = self._thr0
        self.quota_state, self.quota = cpu_quota()
        self.nproc = os.cpu_count()
        self.mem_state, self.mem_peak = _mem_bytes()
        self.mem_rows = []

    def run(self):
        while not self._stop:
            time.sleep(self.every)
            st, now, thr = _cpu_usec()
            if st != "MEASURED":
                continue
            t = time.monotonic() - self.t0
            # cores busy over the interval just elapsed, and seconds the kernel
            # PARKED us in the same window
            self.rows.append((round(t, 3),
                              round((now - self._last) / 1e6 / self.every, 3),
                              round((thr - self._lastthr) / 1e6, 4)))
            self._last, self._lastthr = now, thr
            _ms, _mb = _mem_bytes()
            if _ms == "MEASURED":
                self.mem_rows.append((round(t, 3), _mb))
                if _mb > self.mem_peak:
                    self.mem_peak = _mb

    def stop(self):
        self._stop = True


def run_timed(cmd, cwd, stream_path, timing_path, timeout, env=None,
              stdin_first=None, on_event=None):
    """Run the agent, stamping EVERY stream line the moment it arrives.

    `subprocess.run` returns one buffer at the end, so every arrival time is
    lost and the loop is unmeasurable by construction. This reads line by line
    off the pipe and records a monotonic arrival beside each event.
    """
    import subprocess
    t0 = time.monotonic()
    cpu = CpuSampler(t0)
    cpu.start()
    events = []
    _env = dict(os.environ)
    _env.update(env or {})
    # STDIN STAYS OPEN when the harness is driving the conversation. The agent
    # is no longer handed one prompt and left alone: the source sheet arrives
    # as PIXELS in the first message, and the review sheet as pixels in a
    # SECOND message the harness sends once the placements exist. Those two
    # messages remove five agent turns — a Read of the source sheet, and the
    # preview/curl/tile/Read the review used to cost — because the harness can
    # do all of it without spending a model turn.
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         stdin=subprocess.PIPE if stdin_first else None,
                         text=True, bufsize=1, env=_env)
    killed = False
    # A TIMEOUT THAT ONLY TICKS WHEN OUTPUT ARRIVES IS NOT A TIMEOUT.
    #
    # The deadline below was checked INSIDE `for line in p.stdout`, so it could
    # only fire on a line. A child that goes SILENT — the exact failure the
    # timeout exists for — blocks that loop forever and the check never runs.
    # MEASURED: a 5-second timeout was still running at 30 seconds against a
    # child that printed once and slept. The run then burns to the Modal
    # container timeout instead, and `killed` comes back False, so the record
    # says the agent finished rather than that it hung.
    #
    # It matters more now than it did: the single agent's review pass fires on
    # the agent writing /work/DONE, so "waiting for something that never
    # comes" is a reachable state rather than a theoretical one.
    _killed_by_watchdog = [False]
    _finished = [False]
    _stdin_open = [bool(stdin_first)]
    _io_lock = threading.Lock()

    def _send(msg):
        """Write another user message into the running conversation."""
        if not _stdin_open[0]:
            return False
        # LOCKED, because `send` is no longer called only from the stdout
        # loop. The harness renders the edit on a BACKGROUND thread — a render
        # poll inside the event callback stops this loop reading stdout, the
        # pipe fills, and the agent blocks on a write with nothing in the log
        # to say so. Two threads writing interleaved JSON to one stdin would
        # corrupt both messages and the agent would see neither.
        with _io_lock:
            try:
                p.stdin.write(json.dumps(msg) + "\n")
                p.stdin.flush()
                return True
            except Exception:                                     # noqa: BLE001
                return False

    def _close_stdin():
        """Tell the agent no more input is coming, so it can finish.

        WITHOUT THIS IT HANGS. stream-json input ends at EOF; a stdin left open
        after the last message is a agent waiting for a turn that never
        arrives, which looks exactly like a slow model.
        """
        with _io_lock:
            if _stdin_open[0]:
                _stdin_open[0] = False
                try:
                    p.stdin.close()
                except Exception:                                 # noqa: BLE001
                    pass

    # ON A THREAD, AND THE ROUTE TO THAT IS WORTH KEEPING because I got it
    # wrong in both directions before measuring the right thing.
    #
    # It was synchronous, which was harmless while the first message fitted in
    # the 64K pipe buffer. The single agent's first message carries the ten
    # reference sheets — 27.6 MB — so the parent now blocks here until the
    # child has read it. Whether that deadlocks depends ENTIRELY on what the
    # child does first:
    #
    #   child reads its stdin line first   28 MB write returns in 0.02s, all
    #                                      301 lines arrive, exit 0
    #   child writes before it reads       THE WRITE BLOCKS. The child is
    #                                      blocked writing stdout at 64K, we
    #                                      are blocked writing stdin, and
    #                                      NEITHER DRAIN HAS STARTED YET —
    #                                      the stderr drain and the deadline
    #                                      watchdog are both started AFTER
    #                                      this. Measured: a 10-second timeout
    #                                      had not returned at 60 seconds.
    #
    # The second case is unrecoverable rather than slow: no error, no output,
    # and not even the watchdog is alive to kill it. Which case the real CLI
    # is has not been measured, so this takes the side where being wrong is
    # survivable.
    #
    # It takes the SAME LOCK as `_send`, because a background render can send
    # a message while this write is in flight and two threads interleaving
    # JSON on one stdin corrupts both. The watchdog takes no lock, so it can
    # still kill a run whose write is stuck.
    if stdin_first:
        def _write_first():
            with _io_lock:
                if not _stdin_open[0]:
                    return
                try:
                    p.stdin.write(stdin_first if stdin_first.endswith("\n")
                                  else stdin_first + "\n")
                    p.stdin.flush()
                    return
                except Exception:                                 # noqa: BLE001
                    pass
            _close_stdin()

        threading.Thread(target=_write_first, daemon=True).start()

    # DRAIN STDERR CONCURRENTLY OR THE RUN CAN DEADLOCK. With stderr=PIPE and
    # nobody reading it, a chatty child fills the 64K pipe buffer and blocks on
    # write forever while this loop blocks on stdout. Both sides waiting, no
    # error, no output — a hang that looks exactly like a slow agent, in the
    # harness built to find out why the agent is slow.
    _err = []

    def _drain():
        try:
            for ln in p.stderr:
                _err.append(ln)
        except Exception:                                         # noqa: BLE001
            pass

    _et = threading.Thread(target=_drain, daemon=True)
    _et.start()

    def _watchdog():
        """Kill on the deadline whether or not anything is being printed."""
        while not _finished[0]:
            if time.monotonic() - t0 > timeout:
                _killed_by_watchdog[0] = True
                try:
                    p.kill()
                except Exception:                                 # noqa: BLE001
                    pass
                return
            time.sleep(0.5)

    threading.Thread(target=_watchdog, daemon=True).start()

    # A KILL THE DRIVER CAN CALL. `_close_stdin` only stops the NEXT message;
    # the turn already in progress runs to completion, and a turn can be 28
    # tool calls. Measured on run 9: the spend ceiling closed stdin at
    # assistant event 10 with 2.57M read, and the agent read another 10M
    # across 28 more events before its turn ended — $11.81 on a run the
    # ceiling had "stopped". A ceiling that closes bounds messages; one that
    # kills bounds spend.
    _killed_by_driver = [None]

    def _kill(why="driver"):
        _killed_by_driver[0] = why
        try:
            p.kill()
        except Exception:                                         # noqa: BLE001
            pass

    with open(stream_path, "w", encoding="utf-8") as raw:
        for line in p.stdout:
            t = round(time.monotonic() - t0, 4)
            raw.write(line)
            if time.monotonic() - t0 > timeout:
                killed = True
                p.kill()
                break
            s = line.strip()
            if not s.startswith("{"):
                continue
            try:
                ev = json.loads(s)
            except Exception:                                     # noqa: BLE001
                continue
            if on_event is not None:
                try:
                    try:
                        on_event(ev, _send, _close_stdin, _kill)
                    except TypeError:
                        on_event(ev, _send, _close_stdin)
                except Exception:                                 # noqa: BLE001
                    # A DRIVER FAULT MUST NOT HANG THE RUN. If the injection
                    # raises, stop driving and let the agent finish on its own
                    # rather than waiting forever on a stdin nobody will close.
                    _close_stdin()
            rec = {"t": t, "type": ev.get("type")}
            if ev.get("type") == "stream_event":
                inner = ev.get("event") or {}
                rec["sub"] = inner.get("type")
                if inner.get("type") == "message_delta":
                    rec["final_out_tok"] = (inner.get("usage") or {}).get(
                        "output_tokens")
                if inner.get("type") == "content_block_start":
                    rec["block"] = (inner.get("content_block") or {}).get("type")
                    rec["idx"] = inner.get("index")
                elif inner.get("type") in ("content_block_delta",
                                           "content_block_stop"):
                    rec["idx"] = inner.get("index")
            elif ev.get("type") == "result":
                # THE CLI'S OWN BILL. One event, one total; the authority every
                # per-event sum below is reconciled against.
                rec["result_usage"] = ev.get("usage")
                rec["result_cost_usd"] = ev.get("total_cost_usd")
            elif ev.get("type") == "assistant":
                blocks = (ev.get("message") or {}).get("content") or []
                # ONE ASSISTANT EVENT PER CONTENT BLOCK, EACH REPEATING THE
                # MESSAGE'S USAGE (measured locally 2026-09-17: a thinking +
                # tool_use call arrived as two events, both write=60999). The
                # message id is what makes a sum count a call once.
                rec["msg_id"] = (ev.get("message") or {}).get("id")
                rec["tools"] = [b.get("name") for b in blocks
                                if b.get("type") == "tool_use"]
                # A `Bash: sleep N` is the agent parking the loop ON PURPOSE and
                # it belongs in its own bucket, not folded into TOOL_LOCAL where
                # it reads as work. Measured small so far (12s of 999, 0 of 678)
                # — recorded so it stays visible if it grows.
                rec["cmds"] = [str((b.get("input") or {}).get("command"))[:60]
                               for b in blocks
                               if b.get("type") == "tool_use"
                               and b.get("name") == "Bash"]
                rec["ids"] = [b.get("id") for b in blocks
                              if b.get("type") == "tool_use"]
                u = (ev.get("message") or {}).get("usage") or {}
                rec["out_tok"] = u.get("output_tokens")
                # THE INPUT SIDE, WHICH THIS HAS NEVER RECORDED. Only
                # output_tokens was captured, so the ChatCut path has never
                # measured what its own PREFIX costs — and the question of
                # whether a large cached prefix is affordable is exactly a
                # cache_read question. Without these three fields the answer
                # can only ever be arithmetic.
                #
                # They also settle a question arithmetic cannot: whether a
                # RESUMED session's history is cache_control'd by the CLI. If
                # it is, the history is cache_write once then cache_read at
                # 0.1x; if it is not, it is full input price on EVERY turn,
                # which is roughly a 30x difference on a 129,000-token watch.
                rec["in_tok"] = u.get("input_tokens")
                rec["cache_write_tok"] = u.get("cache_creation_input_tokens")
                rec["cache_read_tok"] = u.get("cache_read_input_tokens")
                # THE PAYLOAD SIZE, not its content. 4,845 tool_use deltas is
                # the volume; which CALL carries it was unattributable because
                # the classifier truncates inputs at 110 chars — a denominator
                # missing again, one layer further in.
                rec["in_chars"] = [len(json.dumps(b.get("input") or {}))
                                   for b in blocks
                                   if b.get("type") == "tool_use"]
            elif ev.get("type") == "user":
                blocks = (ev.get("message") or {}).get("content") or []
                rec["results"] = [b.get("tool_use_id") for b in blocks
                                  if b.get("type") == "tool_result"]
            events.append(rec)
    rc = p.wait()
    # STOP THE WATCHDOG, AND FOLD ITS VERDICT IN. A kill by the watchdog is a
    # timeout exactly as much as a kill by the loop, and reporting only the
    # loop's would say a hung run finished normally.
    _finished[0] = True
    killed = killed or _killed_by_watchdog[0] or bool(_killed_by_driver[0])
    _et.join(timeout=5)
    err = "".join(_err)[-4000:]
    cpu.stop()
    wall = round(time.monotonic() - t0, 3)
    # WHO KILLED IT, NAMED. A run ended by the spend ceiling and one ended by
    # the deadline look identical as `killed=True`; the reason is the
    # difference between "we chose to stop" and "it hung".
    _kill_reason = ("watchdog deadline" if _killed_by_watchdog[0]
                    else _killed_by_driver[0] or None)
    with open(timing_path, "w", encoding="utf-8") as fh:
        json.dump({"wall": wall, "events": events,
                   "killed": bool(killed), "kill_reason": _kill_reason,
                   "cpu_state": cpu.state, "cpu": cpu.rows,
                   "mem_state": cpu.mem_state,
                   "mem_peak_mb": round(cpu.mem_peak / 1048576.0, 1),
                   "mem": cpu.mem_rows,
                   "quota_state": cpu.quota_state, "quota_cores": cpu.quota,
                   "os_cpu_count": cpu.nproc,
                   "throttled_total_s": round(
                       (cpu._lastthr - cpu._thr0) / 1e6, 3)}, fh)
    return rc, err, wall, killed


def partial_messages_supported():
    """(state, bool) — does the installed CLI take --include-partial-messages?

    ASKED, NOT ASSUMED. Without the flag the stream still runs and still
    classifies, and the budget still prints — it just silently folds queue,
    prefill and generation into one bucket, which is the exact split the
    measurement exists to make. A coarser answer that looks identical to a
    finer one is this repo's oldest failure, so the absence is NAMED.
    """
    import subprocess
    try:
        h = subprocess.run(["claude", "--help"], capture_output=True, text=True,
                           timeout=60)
        txt = (h.stdout or "") + (h.stderr or "")
        if not txt.strip():
            return "ABSENT", False
        return "MEASURED", "--include-partial-messages" in txt
    except Exception:                                             # noqa: BLE001
        return "FAILED", False


def budget(timing):
    """Split the wall into WAITING / TTFT / GENERATING / TOOL / NEITHER.

    NEITHER IS THE POINT. It is whatever the clock cannot attribute to the
    model producing tokens or to a tool running, and until now it has been
    invisible inside a 728-second total.
    """
    ev = timing["events"]
    wall = timing["wall"]
    cpu_rows = timing.get("cpu") or []
    cpu_state = timing.get("cpu_state", "ABSENT")

    # WHAT THE TOKENS ARE. 537 of 755 seconds were tokens on the wire, and
    # "the model is generating" is not yet a fix: thinking, prose and tool-call
    # JSON are three different levers (a reasoning budget, a prompt, a schema).
    # The delta events carry their block index, so the stream can say which.
    # PER-TURN, THE SAME QUESTION THE PLANNER NOW ANSWERS. The run-level split
    # says thinking/tool_use/text; it cannot say whether deliberation sits on
    # the turn that DECIDES or is spread across turns that are placing what the
    # plan already settled. On the planner that distinction found a spec turn
    # costing eight times the ruling turn. Here it is derivable from the same
    # stream — message_start to message_stop is one turn — and was simply never
    # taken.
    turn_spans = []     # (t_start, t_end) per assistant turn
    per_turn_block = []  # [{s, blocks}] parallel to turn_spans
    _turn_acc = [{}]     # block seconds accruing inside the open turn
    blocks = {}         # index -> block type
    gen_by_block = {}
    delta_count = {}
    last_delta = {}
    spans = []          # (kind, t_start, t_end)
    pend_tool = {}      # tool_use_id -> (t_emitted, name)
    msg_open = None     # t of message_start awaiting its first delta
    first_delta = None
    prev_t = 0.0
    per_tool = {}
    have_partials = any(e.get("type") == "stream_event" for e in ev)

    for e in ev:
        t, typ, sub = e["t"], e.get("type"), e.get("sub")
        if typ == "stream_event":
            # WHICH TOKENS. thinking / text / tool_use JSON are three different
            # levers — a reasoning budget, a prompt, a schema — and they are
            # indistinguishable inside one GENERATING total. The deltas carry
            # their block index, so the stream can say which.
            if sub == "content_block_start":
                blocks[e.get("idx")] = e.get("block") or "unknown"
            elif sub == "content_block_delta":
                _i = e.get("idx")
                _bt = blocks.get(_i, "unknown")
                if _i in last_delta:
                    gen_by_block[_bt] = round(
                        gen_by_block.get(_bt, 0.0) + (t - last_delta[_i]), 3)
                delta_count[_bt] = delta_count.get(_bt, 0) + 1
                if _i in last_delta:
                    _turn_acc[0][_bt] = round(
                        _turn_acc[0].get(_bt, 0.0) + (t - last_delta[_i]), 3)
                last_delta[_i] = t
            elif sub == "content_block_stop":
                last_delta.pop(e.get("idx"), None)
            if sub == "message_start":
                spans.append(("WAITING", prev_t, t))
                msg_open, first_delta = t, None
            elif sub == "content_block_delta" and msg_open is not None \
                    and first_delta is None:
                first_delta = t
                spans.append(("TTFT", msg_open, t))
            elif sub == "message_stop" and msg_open is not None:
                spans.append(("GENERATING", first_delta or msg_open, t))
                # ONE TURN, CLOSED. Recorded with the block split that accrued
                # inside it, so "which turn was the deliberation" is a read
                # rather than a re-run.
                turn_spans.append((first_delta or msg_open, t))
                _acc = {}
                for _bi, _bt2 in blocks.items():
                    _acc[_bt2] = _acc.get(_bt2, 0.0)
                per_turn_block.append({
                    "s": round(t - (first_delta or msg_open), 2),
                    "blocks": dict(_turn_acc[0])})
                _turn_acc[0] = {}
                msg_open, first_delta = None, None
        elif typ == "assistant":
            if not have_partials:
                # COARSE MODE, and it says so downstream: one bucket for the
                # whole round trip because the deltas were not available.
                spans.append(("MODEL_ROUNDTRIP", prev_t, t))
            for i, nm in zip(e.get("ids") or [], e.get("tools") or []):
                pend_tool[i] = (t, nm)
        elif typ == "user":
            for rid in e.get("results") or []:
                if rid in pend_tool:
                    t0_, nm = pend_tool.pop(rid)
                    local = nm in ("Bash", "Read", "Write", "Glob", "Grep",
                                   "Edit", "ToolSearch", "Skill", "Agent",
                                   "ListAgents", "TodoWrite")
                    spans.append(("TOOL_LOCAL" if local else "TOOL_MCP", t0_, t))
                    per_tool[nm] = round(per_tool.get(nm, 0.0) + (t - t0_), 2)
        prev_t = max(prev_t, t)

    # ── MERGE, because a tool span and a model span can nest ────────────────
    # Summing raw durations double-counts overlap and can exceed the wall,
    # which would make NEITHER negative — an arithmetic statement that the
    # model of what nests is wrong. Occupancy is computed on the UNION.
    by_kind = {}
    for k, a, b in spans:
        by_kind.setdefault(k, []).append((max(0.0, a), max(0.0, b)))
    occupied = []
    for k, iv in by_kind.items():
        iv.sort()
        merged = []
        for a, b in iv:
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        by_kind[k] = round(sum(b - a for a, b in merged), 2)
        occupied += merged
    occupied.sort()
    union, cov = [], 0.0
    for a, b in occupied:
        if union and a <= union[-1][1]:
            union[-1] = (union[-1][0], max(union[-1][1], b))
        else:
            union.append((a, b))
    cov = sum(b - a for a, b in union)
    neither = round(wall - cov, 2)

    # ── WAS THE CONTAINER BUSY IN THE GAPS? ────────────────────────────────
    gaps, c = [], 0.0
    for a, b in union:
        if a - c > 0.5:
            gaps.append((round(c, 2), round(a, 2)))
        c = max(c, b)
    if wall - c > 0.5:
        gaps.append((round(c, 2), round(wall, 2)))

    def cpu_in(a, b):
        pts = [r[1] for r in cpu_rows if a <= r[0] <= b]
        thr = [r[2] for r in cpu_rows if a <= r[0] <= b and len(r) > 2]
        return (round(sum(pts) / len(pts), 3) if pts else None,
                round(sum(thr), 3) if thr else None)

    gap_cpu = [(a, b) + cpu_in(a, b) for a, b in gaps[:40]]
    allcpu = [r[1] for r in cpu_rows]
    # PER-TURN, RETURNED. Unused data is the same defect as unmeasured data.
    _pt = [{"n": _k + 1, "s": _d["s"], "blocks": _d["blocks"]}
           for _k, _d in enumerate(per_turn_block)]
    # ONE ROW PER API CALL, in order, deduped by message id — the table the
    # 624k question is answered from: which call wrote what.
    _seen_ids, _calls = set(), []
    for e in ev:
        if e.get("type") != "assistant" or e.get("cache_read_tok") is None:
            continue
        _mid = e.get("msg_id")
        if _mid and _mid in _seen_ids:
            continue
        _seen_ids.add(_mid)
        _calls.append(e)
    _usage_by_call = [{"n": i + 1, "msg_id": str(e.get("msg_id"))[:16],
                       "tools": e.get("tools") or [],
                       "read": e.get("cache_read_tok"),
                       "write": e.get("cache_write_tok"),
                       "in": e.get("in_tok"), "out": e.get("out_tok")}
                      for i, e in enumerate(_calls)]
    # ONE RESULT EVENT PER USER TURN — pass 1, rewatch 1, rewatch 2 — each
    # carrying THAT turn's usage. final-arch-2's reader took the first and
    # reported a three-turn run's bill as its first turn's ($2.36 of ~$8).
    # The bill is the sum over all of them; the count says how many there were.
    _results = [e for e in ev if e.get("type") == "result" and e.get("result_usage")]
    _rsum = {}
    for _r in _results:
        for _k, _v in (_r.get("result_usage") or {}).items():
            if isinstance(_v, (int, float)) and not isinstance(_v, bool):
                _rsum[_k] = _rsum.get(_k, 0) + _v
    _result = ({"result_usage": _rsum,
                "result_cost_usd": sum((r.get("result_cost_usd") or 0) for r in _results),
                "result_turns": len(_results)} if _results else None)

    return {
        "per_turn": _pt,
        "usage_by_call": _usage_by_call,
        "result_usage": (_result or {}).get("result_usage"),
        "result_cost_usd": (_result or {}).get("result_cost_usd"),
        "result_turns": (_result or {}).get("result_turns", 0),
        # WHO STOPPED IT, IN THE RECORD. A run the ceiling killed, one the
        # experiment stopped after its first batch, and one the deadline
        # killed all read killed=True; the reason is the difference between
        # chose-to-stop and hung, and the arm report has to say which.
        "killed": bool(timing.get("killed")),
        "kill_reason": timing.get("kill_reason"),
        "wall_s": wall,
        "mode": "PARTIAL_MESSAGES" if have_partials else
                "COARSE (no deltas — queue, prefill and generation are ONE bucket)",
        "buckets_s": by_kind,
        "attributed_s": round(cov, 2),
        "neither_s": neither,
        "neither_share": round(100.0 * neither / wall, 1) if wall else None,
        "cpu_state": cpu_state,
        "cpu_mean_cores": round(sum(allcpu) / len(allcpu), 3) if allcpu else None,
        "cpu_p90_cores": (sorted(allcpu)[int(0.9 * len(allcpu))]
                          if allcpu else None),
        # `Agent` IS NOT A LOCAL TOOL IN ANY USEFUL SENSE. It is a whole
        # nested agent loop — its own generation, its own tool calls — and
        # charging it to TOOL_LOCAL made 152s of a SUBAGENT'S TOKENS read as
        # CLI overhead. Broken out so the headline never says that again.
        "nested_agent_s": round(per_tool.get("Agent", 0.0), 2),
        "generating_by_block_s": dict(sorted(gen_by_block.items(),
                                              key=lambda kv: -kv[1])),
        "tool_seconds_by_name": dict(sorted(per_tool.items(),
                                            key=lambda kv: -kv[1])[:14]),
        # 407 tokens against 458 seconds of streaming was not a measurement,
        # it was a PARTIAL SUM WEARING A TOTAL'S CLOTHES: most assistant events
        # carry no usage block, so the sum silently covered a handful of turns.
        # Report the denominator beside it and let a thin sample say so.
        "output_tokens": {
            # DEDUPED BY MESSAGE ID. The previous sums ran over every assistant
            # event and over-counted every multi-block call by its block
            # count — final-arch-1 read "2,725,573" over 10 events for 6
            # calls. `_calls` keeps the first event of each message id.
            "dedupe": "BY MESSAGE ID — one assistant event per content block "
                      "repeats the message usage (measured 2026-09-17)",
            "api_calls": len(_calls),
            "in_sum": sum(e.get("in_tok") or 0 for e in _calls
                          if e.get("in_tok") is not None),
            "cache_write_sum": sum(e.get("cache_write_tok") or 0 for e in _calls
                                   if e.get("cache_write_tok") is not None),
            "cache_read_sum": sum(e.get("cache_read_tok") or 0 for e in _calls
                                  if e.get("cache_read_tok") is not None),
            "sum": sum(e.get("out_tok") or 0 for e in ev
                       if e.get("type") == "assistant"),
            "from_events": sum(1 for e in ev if e.get("type") == "assistant"
                               and e.get("out_tok")),
            "of_assistant_events": sum(1 for e in ev
                                       if e.get("type") == "assistant"),
            # WRONG, AND THE COVERAGE CHECK SAID MEASURED. Every assistant
            # event carried a usage block, so "is it present on every turn"
            # passed — and the value is still nonsense: 525 tokens against
            # 5,408 streamed deltas. With --include-partial-messages the
            # `assistant` event's usage is the message_start figure
            # (output_tokens ~1), not the final count, which lands in
            # `message_delta`. A check that asks about COVERAGE cannot see a
            # field that is present, well-typed and the wrong field.
            # Until this reads message_delta, the honest quantity is
            # `delta_count_by_block` and this one is labelled UNTRUSTWORTHY.
            "state": "UNTRUSTWORTHY — reads message_start usage, not the "
                     "final count; use delta_count_by_block",
        },
        "delta_count_by_block": delta_count,
        "output_tokens_final": {
            "sum": sum(e.get("final_out_tok") or 0 for e in ev),
            "from_message_delta_events": sum(1 for e in ev
                                             if e.get("final_out_tok")),
        },
        "gaps_over_0s5": len(gaps),
        "gap_detail": gap_cpu,
        "quota_state": timing.get("quota_state"),
        "quota_cores": timing.get("quota_cores"),
        "os_cpu_count": timing.get("os_cpu_count"),
        "throttled_total_s": timing.get("throttled_total_s"),
        "throttled_share": (
            round(100.0 * (timing.get("throttled_total_s") or 0) / wall, 1)
            if wall else None),
    }
