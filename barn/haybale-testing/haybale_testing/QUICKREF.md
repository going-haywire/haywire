# testing — component index (v0.0.39)

## node
- `testing:node:BenchBareNode` — Bench Bare Node — FROZEN: minimal no-port control node for measuring _execute dispatch overhead.  _tags: benchmark, frozen, bare, dispatch_
- `testing:node:BenchExecNode` — Bench Exec Node — FROZEN: minimal EXEC in→out conduit for measuring control-edge payload forwarding.  _tags: benchmark, frozen, exec, conduit, control-edge_
- `testing:node:ControlPayloadTestNode` — Control Payload TestNode — Test-only control node for exercising EXEC-edge payloads. Records the payload that arrived on its exec inlet, then advances — optionally writing its own payload, optionally forwarding the entered one implicitly (transparent conduit).  _tags: test, control, exec, payload, conduit_
- `testing:node:DisplayNode` — Display — Displays input values for debugging  _tags: display, debug, output, basic_
- `testing:node:DynamicPortTestNode` — Dynamic Port TestNode —   _tags: testing, dynamic, push, pop, reconfigure_
- `testing:node:EdgeLinkTestNode` — Edge Link TestNode —   _tags: testing, edge, link, inlet, outlet, connection, adapter_
- `testing:node:PerformanceTester` — Performance Testing Node — Helps test performance of execution system  _tags: performance, control, flow, event_
- `testing:node:SettingsNode` — Settings Test Node — Test the Settings for debugging  _tags: settings, debug, test, example_
- `testing:node:SizeBoxAspectNode` — Size Box (declared width) — Hosts an oversized widget declaring min_width only  _tags: size, resize, widget, testing_
- `testing:node:SizeBoxContentNode` — Size Box (content-sized) — Hosts an oversized widget with no declared box  _tags: size, resize, widget, testing_
- `testing:node:SizeBoxFixedNode` — Size Box (declared box) — Hosts an oversized widget declaring both axes  _tags: size, resize, widget, testing_
- `testing:node:TestAddFloatNode` — Test Add Float — Test arithmetic node — adds two float values  _tags: test, math, add, float, arithmetic_
- `testing:node:TestBeginPlayNode` — Test Begin Play — Test version of BeginPlay — triggered once when execution starts  _tags: test, start, init, begin, event_
- `testing:node:TestCustomCallbackNode` — Test Custom Callback — Test version of CustomCallback — listens for named callbacks  _tags: test, callback, listen, event, custom_
- `testing:node:TestEmitCallbackNode` — Test Emit Callback — Test version of EmitCallback — emits a callback to trigger event nodes  _tags: test, callback, emit, trigger, event_
- `testing:node:TestGroupAndSectionNode` — Group And Sections — Tests Rendering for Group and Sections  _tags: test, group, section, render_
- `testing:node:TestPrintNode` — Test Print — Test version of Logger — logs a message and continues flow  _tags: test, print, log, message, terminal_

## type
- `testing:type:TEST_BOOL` — Boolean — True or False
- `testing:type:TEST_FLOAT` — Float — Decimal numberer
- `testing:type:TEST_INT` — Integer — Whole number
- `testing:type:TEST_STRING` — String — Text data
- `testing:type:TEST_TEMPERATURE` — Temperature — Temperature in Celsius

## adapter
- `testing:adapter:BoolToIntAdapter` — BoolToIntAdapter — Convert bool to integer
- `testing:adapter:FloatToStringAdapter` — FloatToStringAdapter — Convert float to string
- `testing:adapter:IntToFloatAdapter` — IntToFloatAdapter — Convert integer to float

## widget
- `testing:widget:AspectBoxWidget` — AspectBoxWidget — Oversized content behind a declared width; height follows the content's aspect
- `testing:widget:FixedBoxWidget` — FixedBoxWidget — Oversized content behind a fully declared box
- `testing:widget:OversizedContentWidget` — OversizedContentWidget — Oversized content that sizes from its contents (no declared box)

## setting
- `testing:setting:TestingSettings` — Testing — 

## farmhand
- `testing:farmhand:affinity` — Affinity — Report handler thread and loop.
- `testing:farmhand:block` — Block — Sleep off-loop for `seconds`.
- `testing:farmhand:echo` — Echo — Echo text back (canned read tool).
- `testing:farmhand:fail` — Fail — Always fails with a stable code.

## state
- `testing:state:TestSessionState` — Test Session State — 

## panel
- `testing:panel:TestCopyNodeMenuPanel` — Copy Node — 
- `testing:panel:TestCopySelectionMenuPanel` — Copy Selection — 
- `testing:panel:TestCreateNodeMenuPanel` — Create Node — 
- `testing:panel:TestDeleteEdgeMenuPanel` — Delete Connection — 
- `testing:panel:TestDeleteNodeMenuPanel` — Delete Node — 
- `testing:panel:TestEdgeErrorsMenuPanel` — Connection Errors — 
- `testing:panel:TestEdgePathMenuPanel` — Connection Path — 
- `testing:panel:TestEdgeWarningsMenuPanel` — Connection Warnings — 
- `testing:panel:TestInspectEdgeMenuPanel` — Inspect Connection — 
- `testing:panel:TestPasteSelectionMenuPanel` — Paste — 
- `testing:panel:TestRedrawNodeMenuPanel` — Redraw Node — 
- `testing:panel:TestResetNodeMenuPanel` — Reset Node — 
- `testing:panel:TestRevalidateNodeMenuPanel` — Revalidate Node — 
- `testing:panel:TestSessionStateMenuPanel` — Test SessionState Panel —
