# Testing strategy for Farmhand

Type: grilling
Status: resolved
Blocked by: 05
Resolved: 2026-07-19

## Question

How are Farmhand's server, tools, and notification behavior tested inside the existing pytest harness — what does the spec commit to?

Graduated from fog once the process model settled (ticket 04: in-process mount on the studio app, official `mcp` SDK v1.x). To settle:

- **Harness shape**: an in-process MCP *client* fixture (the `mcp` package ships a client; FastMCP documents client-side `list_changed` handling useful for integration tests) against an app-shaped test server — does this fit the existing `unit` / `integration` markers, and does it need the Playwright-ordering rules (`browser` marker, browser-tests-last) from `tests/conftest.py`?
- **What must be covered**: tool add/remove on library enable/disable/hot-reload with `list_changed` observed by a real client; loop-affinity correctness for mutating tools; auth/Origin rejection paths (per ticket 06's outcome); baseline tools on a bare studio.
- **DI hygiene**: tests touching the ambient DI context must respect the `test_injector` snapshot/restore rules (never `create_test_injector()` directly) — what fixture shape does Farmhand testing add, if any?
- Whether the transport prototype (ticket 09) graduates into the permanent test harness or stays throwaway.

## Answer

Grilled 2026-07-19 (tests/conftest.py read first — test_injector snapshot/restore, session-scoped library_system idiom, marker set and browser-last ordering confirmed as assumptions). All forks user-confirmed:

1. **Two tiers on existing markers; NO browser tests in v1.**
   - `unit`: `FarmhandToolRegistry` mechanics, schema derivation, naming + `studio`-reservation, annotations — no server; plus `SetPropertyAction` unit tests beside the nine existing action-class suites.
   - `integration`: real served app + the SDK's real streamable-HTTP client. Rejected: in-memory MCP sessions (skips mount, lifespan runner, transport security — exactly where the prototype found reality biting) and a v1 Playwright test (tests the join of two already-tested contracts; noted as an optional later addition).
2. **Fixture architecture** (`tests/farmhand/conftest.py`):
   - `farmhand_server` — session-scoped, mirrors the `library_system` fixture idiom (full barn libraries, sets/clears global injector pair, never `create_test_injector` directly), mounts via the prototype-proven single-runner-task pattern, uvicorn in a background thread on an ephemeral port.
   - `farmhand_client` — fresh SDK `ClientSession` per test with its own `asyncio.run` (no parked-loop hazard; not `browser`-marked).
   - Bare-studio variant fixture (no contributing libraries) for the baseline-tools contract.
   - Test MCP components (canned read tool, canned failing tool, instrumented affinity tool) live in **haybale-testing**'s new `mcp/` folder; enabling/disabling that library is the lifecycle trigger.
   - Tests clean up haystack entries they create. Rejected: function-scoped server (seconds per boot — kills the fast loop), reusing the browser harness app (inherits `browser` marking/ordering).
3. **Coverage table the spec commits to** (each row traces to a decided behavior from tickets 04–08):
   | Tier | Contract |
   |---|---|
   | unit | registry add/evict on enable/disable; schema derivation (types/defaults/override); naming + `studio` reservation; annotations |
   | unit | `SetPropertyAction` undo/redo/serialization |
   | integration | initialize advertises `listChanged: true` (regression vs the SDK-default quirk the prototype confirmed) |
   | integration | tool round-trip structured JSON; structured error contract (code/message/ids, no traceback) |
   | integration | disable/enable haybale-testing → client observes `tools/list_changed` → `tools/list` shrinks/grows |
   | integration | mutating tool on the loop (instrumented tool asserts thread/loop); blocking tool via `offload()` doesn't stall a concurrent request |
   | integration | one tool call = one undo fence (two calls, one `undo` reverts exactly one) |
   | integration | auth: missing/wrong token → 401; disallowed Origin rejected; token file created gitignored on first start |
   | integration | bare-studio fixture serves exactly the baseline tools |
4. **The prototype stays a throwaway asset** (ticket 09's link): its patterns (runner task, client shape, affinity instrumentation) are lifted into the real fixture; its code (private `_entries` access, prints) is not.

This was the map's final decision ticket — Final spec assembly (11) is now unblocked and is the only open ticket.
