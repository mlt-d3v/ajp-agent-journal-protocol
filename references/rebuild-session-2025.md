# AJP Rebuild Session Notes

## Context
Previous session built Phases 1-4 (185 tests) but files were not persisted to disk. Full rebuild required plus Phase 5 (Temporal workflow + OpenTelemetry).

## Bugs Fixed During Rebuild

### ed25519 SigningKey constructor
`SigningKey()` with no args fails on this version. Must pass seed: `SigningKey(os.urandom(32))`.

### VerifyingKey.verify() return value
Returns `None` on success, not `True`. Chain verification must check `is None`.

### PriorityEntry dataclass unpacking
`heapq.heappop()` returns `PriorityEntry` object, not tuple. Was doing `_, entry = heapq.heappop()` which fails. Fix: `item = heapq.heappop(); batch.append(item.entry)`.

### RBAC SecretLevel string comparison
`SecretLevel.LOW.value` is `"low"`, string comparison `"critical" > "low"` is True alphabetically but semantically wrong. Fixed with ordinal lookup list.

### PromptSanitizer quarantine threshold
Original threshold 0.5 was too lenient -- single pattern match scored 0.25 and did not trigger quarantine. Lowered to 0.25.

### JournalEntry hash determinism
`datetime.utcnow()` means two entries created at different microseconds get different hashes. Test fixed by using fixed timestamp.

### json.dumps datetime serialization
`compute_hash()` serializes datetime which needs `default=str` in `json.dumps()`.

### Checkpoint.from_dict key mapping
`to_dict()` uses `"type"` key but constructor expects `checkpoint_type`. `from_dict()` must `pop("type")` and re-key.

### Workflow context passing
Step handlers receive context dict but the engine stores results in `context["step_results"]` keyed by step name. Original test tried to mutate context directly which didn't work with the handler pattern.

## Final Test Count
- Phase 1: 27 tests
- Phase 2: 35 tests
- Phase 3: 49 tests
- Phase 4: 74 tests
- Phase 5: 54 tests (new)
- Total: 197 tests passing
