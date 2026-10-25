# @als-apg/dock-engine

The dock layout engine shared by OSPREY and CANOPY: the layout model and its
validation, geometry, drop planning, open/close/reopen, and hit-testing, as
pure functions with no DOM and no runtime dependencies. It ships with the
golden case files (`cases/`) that pin the engine's behaviour, and a case runner
(`./cases`) that replays them against any implementation of the engine.

## How each consumer gets it

- **OSPREY web terminal** — a generated vendor copy of `dist/dock-engine.mjs`.
- **CANOPY screen runtime** — a git dependency on `@als-apg/dock-engine`.
- **CANOPY backend** — the Python distribution `osprey-dock-engine`
  (`import dock_engine`), built from this same directory, which carries the
  case files and `dist/manifest.json` as package data.

The package is versioned with OSPREY's CalVer release tags; `0.0.0-dev` in
`package.json` marks an untagged checkout. It is not published to a registry.

## Public API

- `@als-apg/dock-engine` — the engine (`dist/dock-engine.mjs`, types in
  `dist/dock-engine.d.mts`).
- `@als-apg/dock-engine/cases` — the case runner (`loadCases`, `runCase`,
  `checkCase`, `CASES_DIR`, the case types); imports only `node:fs`,
  `node:module`, `node:path` and the engine.
- `@als-apg/dock-engine/cases/<kind>/<name>.json` — the case files.

## Source of truth

`ts/` and `cases/` are edited in the package and rebuilt with
`node packages/dock-engine/scripts/build.mjs`; `dist/`, vendor copies and
consumer installs are generated, never edited.

## Provenance

The engine was cut over on 2026-10-24 from the CANOPY screen runtime
(`als-apg/canopy-osprey-mirror-screen-runtime` at `386c66cb`,
`apps/viewer/src/workspace/dock/model/`). At the cutover every refusing
validate case gained a `where` field. `CUTOVER.json` records the exact
provenance: the source digest, the blob of each imported file, the 42
exported names, and the case counts.
