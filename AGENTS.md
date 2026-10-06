# Notes for coding agents

Guidance for Codex, Claude Code, and similar tools working in this repository.

## Keep the Studio Lot view in step

The Studio Lot (`/lot`, files `web/lot.html`, `web/lot.css`, `web/lot.js`, `web/lot-scene.js`) is a second front end over the same API as the classic view. New data appears in it automatically; new concepts do not.

When a change does any of the following, update the Studio Lot in the same change, following the matching recipe in [STUDIO_LOT.md](STUDIO_LOT.md):

- adds, removes, or renames an agent in `agents/master_agent.py`
- adds, renames, or removes a field in the saved report JSON or in `utils/report_library.py`
- adds a recommendation value beyond GO / CONDITIONAL GO / NO-GO
- adds or renames a progress event or pipeline stage
- adds an input to `AnalysisRequest` in `web_app.py` that a user should be able to set

If a change touches none of these, leave the Studio Lot alone.

## Checks

- Run `python -m unittest discover -s tests` before finishing. One test fails when the agent list in `web/lot.js` and the orchestrator disagree.
- Do not commit anything under `outputs/`; the test suite writes fixtures there.
- `web/vendor/three.module.min.js` is a vendored library. Do not edit it.
