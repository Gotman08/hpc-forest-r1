"""Account for the native CLI's cumulative conversation counters once per turn."""
from __future__ import annotations

import copy


def conversation_usage(response, previous, turn):
    """Return a durable counter and replace only verified cumulative usage by deltas.

    The CLI's turn.completed event reports total_token_usage for the persisted
    thread, including earlier resumes. Its raw events remain in the response.
    A missing prior counter or a reset cannot establish the current turn's cost.
    """
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None
    events = copy.deepcopy(usage.get("events") or [])
    last = events[-1] if events and isinstance(events[-1], dict) else {}
    fields = ("input_tokens", "output_tokens")
    current = {k:last[k] for k in last if type(last[k]) is int and last[k] >= 0}
    if not all(k in current for k in fields):
        current = None
    before = {k:0 for k in current} if turn == 0 and current else (previous or {}).get("usage_cumulative")
    exact = (usage.get("token_accounting") == "exact" and current is not None
             and isinstance(before, dict) and all(type(before.get(k)) is int
                 and 0 <= before[k] <= current[k] for k in fields))
    delta = ({k:v-before[k] for k,v in current.items()
              if type(before.get(k)) is int and 0 <= before[k] <= v} if exact else None)
    tokens = sum(delta[k] for k in fields) if exact else None
    usage.update(tokens=tokens, observed_tokens=tokens, token_accounting="exact" if exact else "unknown",
                 events=[delta] if delta else [], native_cumulative_events=events,
                 native_cumulative_tokens=sum(current[k] for k in fields) if current else None,
                 accounting_scope="native_conversation_delta",
                 accounting_note="Current cumulative counter minus the preceding verified turn" if exact
                 else "Missing, reset or unverified native conversation counter; no zero cost inferred")
    return current
