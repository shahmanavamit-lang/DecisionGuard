# Generated phase-seven evaluation

Synthetic deterministic policy ablations. No external benchmark, LLM, threat-population confidence interval or production guarantee. Timing includes SQLite and excludes fixture setup; full case elapsed includes setup. CPU and peak RSS cover the entire evaluation process (including setup), not isolated per-case workers. Database bytes are storage, not RAM. Submit/dispatch timings cover supplier/probe calls only, not inventory dispatch or model inference.

| Mode | Harmful effects / attempts | Clean tasks | Attacked tasks | Independent steps | Benign interventions |
| --- | --- | --- | --- | --- | --- |
| credentials_model | 20/20 | 15/15 | 0/20 | 10/10 | 0/35 |
| rules_only | 5/20 | 15/15 | 15/20 | 10/10 | 0/35 |
| selective | 5/20 | 10/15 | 10/20 | 10/10 | 5/35 |
| whole_pause | 5/20 | 10/15 | 0/20 | 0/10 | 10/35 |

Gates: {"explicit_scope_effects_absent": true, "independent_work_preserved": true, "dependent_work_paused": true, "duplicate_effect_absent": true, "expiry_blocks_dispatch": true}

Overbroad-scope harm is intentionally included: a valid but wrongly broad policy can permit harmful use. Benign novelty can still be held. These are measured limitations, not hidden exclusions.
