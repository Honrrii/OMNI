"""
OMNI Frontier Research — Phase 1 protocol/experiment contracts.

This package only defines and validates data shapes for the Claude <-> Codex
frontier research protocol: messages (`protocol.py`), experiment records and
scoring (`experiments.py`), and branch/isolation safety classification
(`safety.py`). It does not send a message anywhere, launch a model, invoke
Codex, run an autonomous loop, or touch git.

See `.omni-lab/README.md` and `.omni-lab/protocols/` for the workflow these
shapes are meant to support, and `docs/agentic/` for OMNI's existing
(separate) Auto Dev production protocol — the two are related in spirit but
are not the same workflow. Frontier Research is exploratory and disposable;
Auto Dev production is the bounded implement/review/merge path.
"""
from __future__ import annotations
