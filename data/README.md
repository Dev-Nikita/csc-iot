# data/

`raw/` — append-only experiment output. Never edited, never committed. One directory per `experiment_id`, matching a manifest in `experiments/manifests/`.

`processed/` — derived exclusively by versioned scripts in `analysis/`. Anything here can be deleted and regenerated; if it cannot, that is a bug.

Schema documentation lands here at Phase 7, together with the split definitions from `EXPERIMENT_PROTOCOL.md` §6. Replay-branch records carry `is_replay_branch = true` and are quarantined from every training set; a leakage test enforces this.
