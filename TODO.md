# Brainpack — Roadmap & Todo

## Phase 0 — Pre-open-source cleanup

- [x] Rename MCP tool commands — drop `brainpack_` prefix, use short names
- [x] Remove `chat` from MCP tools (redundant with `query` in one-shot context)
- [ ] Refactor file structure — break up long files, better module organization
- [ ] Audit and remove redundant tests
- [ ] Add `.planning/` to `.gitignore`
- [ ] Write `README.md`
- [ ] Set version to `0.1.0` in `pyproject.toml`

## Phase 1 — Open source launch

- [ ] Create `packs/` folder with 2-3 seed packs (`pack.yaml` per pack)
- [ ] Add `brainpack install <slug>` command — fetches from raw.githubusercontent.com
- [ ] Publish repo publicly
- [ ] Submit `SKILL.md` to ClawHub registry

## Phase 2 — Post-launch features

- [ ] Add `brainpack serve` command — SSE transport, `--host`, `--port`, `--token` flags
- [ ] Static brainpack.dev page — pack list, install instructions, docs

## Phase 3 — After community traction

- [ ] OpenClaw ContextEngine plugin — proactive context injection from installed packs
- [ ] Add wishlist/email capture to brainpack.dev if demand is there

## Decisions locked in

- No premium hosted endpoint (copyright risk, not worth it yet)
- No version tracking / official vs customized pack states until registry exists
- `doctor` command stays (useful for open source debugging)
- `evidence` name stays
- `chat` removed from MCP, kept in CLI (interactive mode)
- Version starts at `0.1.0` not `1.0.0`
