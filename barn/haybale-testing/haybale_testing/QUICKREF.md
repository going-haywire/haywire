# haybale-testing — component index (v0.1.3)

## node
- `haybale-testing:node:BenchBareNode` — Bench Bare Node — FROZEN: minimal no-port control node for measuring _execute dispatch overhead.  _tags: benchmark, frozen, bare, dispatch_
- `haybale-testing:node:BenchExecNode` — Bench Exec Node — FROZEN: minimal EXEC in→out conduit for measuring control-edge payload forwarding.  _tags: benchmark, frozen, exec, conduit, control-edge_
- `haybale-testing:node:ControlPayloadTestNode` — Control Payload TestNode — Test-only control node for exercising EXEC-edge payloads. Records the payload that arrived on its exec inlet, then advances — optionally writing its own payload, optionally forwarding the entered one implicitly (transparent conduit).  _tags: test, control, exec, payload, conduit_
- `haybale-testing:node:DisplayNode` — Display — Displays input values for debugging  _tags: display, debug, output, basic_
- `haybale-testing:node:DynamicPortTestNode` — Dynamic Port TestNode —   _tags: testing, dynamic, push, pop, reconfigure_
- `haybale-testing:node:EdgeLinkTestNode` — Edge Link TestNode —   _tags: testing, edge, link, inlet, outlet, connection, adapter_
- `haybale-testing:node:PerformanceTester` — Performance Testing Node — Helps test performance of execution system  _tags: performance, control, flow, event_
- `haybale-testing:node:SettingsNode` — Settings Test Node — Test the Settings for debugging  _tags: settings, debug, test, example_
- `haybale-testing:node:SizeBoxAspectNode` — Size Box (declared width) — Hosts an oversized widget declaring min_width only  _tags: size, resize, widget, testing_
- `haybale-testing:node:SizeBoxContentNode` — Size Box (content-sized) — Hosts an oversized widget with no declared box  _tags: size, resize, widget, testing_
- `haybale-testing:node:SizeBoxFixedNode` — Size Box (declared box) — Hosts an oversized widget declaring both axes  _tags: size, resize, widget, testing_
- `haybale-testing:node:TestAddFloatNode` — Test Add Float — Test arithmetic node — adds two float values  _tags: test, math, add, float, arithmetic_
- `haybale-testing:node:TestBeginPlayNode` — Test Begin Play — Test version of BeginPlay — triggered once when execution starts  _tags: test, start, init, begin, event_
- `haybale-testing:node:TestCustomCallbackNode` — Test Custom Callback — Test version of CustomCallback — listens for named callbacks  _tags: test, callback, listen, event, custom_
- `haybale-testing:node:TestEmitCallbackNode` — Test Emit Callback — Test version of EmitCallback — emits a callback to trigger event nodes  _tags: test, callback, emit, trigger, event_
- `haybale-testing:node:TestGroupAndSectionNode` — Group And Sections — Tests Rendering for Group and Sections  _tags: test, group, section, render_
- `haybale-testing:node:TestPrintNode` — Test Print — Test version of Logger — logs a message and continues flow  _tags: test, print, log, message, terminal_

## type
- `haybale-testing:type:TEST_BOOL` — Boolean — True or False
- `haybale-testing:type:TEST_FLOAT` — Float — Decimal numberer
- `haybale-testing:type:TEST_INT` — Integer — Whole number
- `haybale-testing:type:TEST_STRING` — String — Text data
- `haybale-testing:type:TEST_TEMPERATURE` — Temperature — Temperature in Celsius

## adapter
- `haybale-testing:adapter:BoolToIntAdapter` — BoolToIntAdapter — Convert bool to integer
- `haybale-testing:adapter:FloatToStringAdapter` — FloatToStringAdapter — Convert float to string
- `haybale-testing:adapter:IntToFloatAdapter` — IntToFloatAdapter — Convert integer to float

## widget
- `haybale-testing:widget:AspectBoxWidget` — AspectBoxWidget — Oversized content behind a declared width; height follows the content's aspect
- `haybale-testing:widget:FixedBoxWidget` — FixedBoxWidget — Oversized content behind a fully declared box
- `haybale-testing:widget:OversizedContentWidget` — OversizedContentWidget — Oversized content that sizes from its contents (no declared box)

## setting
- `haybale-testing:setting:TestingSettings` — Testing — 

## farmhand
- `haybale-testing:farmhand:affinity` — Affinity — Report handler thread and loop.
- `haybale-testing:farmhand:block` — Block — Sleep off-loop for `seconds`.
- `haybale-testing:farmhand:echo` — Echo — Echo text back (canned read tool).
- `haybale-testing:farmhand:fail` — Fail — Always fails with a stable code.

## state
- `haybale-testing:state:TestSessionState` — Test Session State — 

## panel
- `haybale-testing:panel:TestCopyNodeMenuPanel` — Copy Node — 
- `haybale-testing:panel:TestCopySelectionMenuPanel` — Copy Selection — 
- `haybale-testing:panel:TestCreateNodeMenuPanel` — Create Node — 
- `haybale-testing:panel:TestDeleteEdgeMenuPanel` — Delete Connection — 
- `haybale-testing:panel:TestDeleteNodeMenuPanel` — Delete Node — 
- `haybale-testing:panel:TestEdgeErrorsMenuPanel` — Connection Errors — 
- `haybale-testing:panel:TestEdgePathMenuPanel` — Connection Path — 
- `haybale-testing:panel:TestEdgeWarningsMenuPanel` — Connection Warnings — 
- `haybale-testing:panel:TestInspectEdgeMenuPanel` — Inspect Connection — 
- `haybale-testing:panel:TestPasteSelectionMenuPanel` — Paste — 
- `haybale-testing:panel:TestRedrawNodeMenuPanel` — Redraw Node — 
- `haybale-testing:panel:TestResetNodeMenuPanel` — Reset Node — 
- `haybale-testing:panel:TestRevalidateNodeMenuPanel` — Revalidate Node — 
- `haybale-testing:panel:TestSessionStateMenuPanel` — Test SessionState Panel — 

## theme
- `haybale-testing:theme:TestLightTheme` — Test Light —
