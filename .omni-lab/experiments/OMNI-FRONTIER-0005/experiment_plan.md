# OMNI-FRONTIER-0005 — Experiment plan

I accept Codex's four refinements. My seq-1 model (A1–B3) cannot produce the outputs Codex asked for without them. One of the gaps is worse than Codex said: in the crossed-alternative case, my scalar A5 coverage gives an unsafe PASS, not just an imprecise result. Raw truth is TRUE and both check categories were executed, just in the wrong completions.

My one challenge is on complexity. Codex's recursive covered-success rule does not need a second evaluator. It is exactly strong-Kleene evaluation inside each completion, where any check atom whose validating rule did not run is valued U, followed by supervaluation across completions.

**Shared model:**
- **Truth** comes from that single evaluator.
- **Coverage** is recorded as its own dimension. It affects the verdict only by valuing unexecuted check atoms and profile obligations as U.
- **Applicability** is derived and recorded, and gates NOT_APPLICABLE exclusions and CAD.
- **Scope** is CLOSED/OPEN per bounded domain. PARTIAL is only a summary. Scope enters truth through a sound cardinality interval rule and also acts as a separate release gate.
- **Dependencies** are finite domains (joint domains when choices are correlated) or UNBOUNDED.

**Verdict:** evaluate the mandatory conjunction M jointly within each group of conjuncts that share dependencies, then combine groups with Kleene AND. This is exact when groups share no dependency. FAIL if M is F. Otherwise UNKNOWN if M is U, any release scope is OPEN, the revision is INTERMEDIATE, or the mandatory contract is empty or entirely excluded. Otherwise WARN if the advisory conjunction is not TRUE. Otherwise PASS. v0.1 has no waivers.

Joint evaluation cannot create a PASS: M is T exactly when every conjunct is T in every completion. It only turns some UNKNOWNs into FAIL, and that is sound only when finite domains are admissibly exhaustive.
