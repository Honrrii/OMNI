# Frontier Research Conversations

Raw thread message logs, one file per thread ID:

```text
.omni-lab/conversations/OMNI-FRONTIER-XXXX.jsonl
```

Each line is one `FrontierMessage` (`omni/frontier/protocol.py`) serialized
as JSON — `omni.frontier.protocol.to_json` per message, or the whole thread
assembled with one message per line (JSON Lines, not a single JSON array,
so a thread can be appended to without rewriting the whole file).

## When a conversation stays here vs. becomes an experiment

A thread lives in this directory for as long as it's exploratory:
`HYPOTHESIS`, `COUNTER_HYPOTHESIS`, `CHALLENGE`, `RESPONSE`,
`REVIEW_REQUEST`/`REVIEW_FINDING` exchanges that are still narrowing down
whether there's a real, testable question here at all.

The moment a thread produces an `EXPERIMENT_PROPOSAL` that gets accepted,
it should get a full archive under `../experiments/OMNI-FRONTIER-XXXX/`
(see that directory's `README.md`) — `messages.jsonl` there continues from
this file rather than starting a second, disconnected log for the same
thread ID.

A thread that never escalates past exploratory back-and-forth — no
experiment ever got proposed, or the idea was dropped as insufficiently
grounded per the Novelty Rule (`../protocols/EXPERIMENT_LIFECYCLE.md`) —
stays here permanently. It is still worth keeping: a future session
deciding whether to open a new thread on a similar topic should check here
first, the same way it would check `../experiments/` for a prior formal
result.
