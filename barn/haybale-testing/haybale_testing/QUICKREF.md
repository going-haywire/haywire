# haybale-testing — component index (v0.6.4)

## node
- `haybale-testing:node:AddFloatProbeNode` — Add Float Probe — Test arithmetic node — adds two float values  _tags: test, math, add, float, arithmetic_
- `haybale-testing:node:AddPortProbeNode` — Add Port Probe —   _tags: testing, add, placeholder, resolve, variadic_
- `haybale-testing:node:ArrayCallbackProbeNode` — Array Callback Probe — Test-only: an array-of-CALLBACK outlet and inlet.  _tags: test, array, callback, container_
- `haybale-testing:node:ArrayExecProbeNode` — Array Exec Probe — Test-only: an array-of-EXEC outlet and inlet on a control node.  _tags: test, array, exec, container_
- `haybale-testing:node:BeginPlayProbeNode` — Begin Play Probe — Test version of BeginPlay — triggered once when execution starts  _tags: test, start, init, begin, event_
- `haybale-testing:node:BenchBareNode` — Bench Bare — FROZEN: minimal no-port control node for measuring _execute dispatch overhead.  _tags: benchmark, frozen, bare, dispatch_
- `haybale-testing:node:BenchDataPassNode` — Bench Data Pass — FROZEN: data node passing x + 1 on, for measuring data-flow evaluation.  _tags: benchmark, frozen, data, chain_
- `haybale-testing:node:BenchDataRaiseNode` — Bench Data Raise — FROZEN: data node whose worker always raises, for measuring the failure path.  _tags: benchmark, frozen, data, raise, failure_
- `haybale-testing:node:BenchExecNode` — Bench Exec — FROZEN: minimal EXEC in→out conduit for measuring control-edge payload forwarding.  _tags: benchmark, frozen, exec, conduit, control-edge_
- `haybale-testing:node:BenchFanInNode` — Bench Fan In — FROZEN: data node adding two inputs, for measuring a fan-in in data-flow evaluation.  _tags: benchmark, frozen, data, fan-in_
- `haybale-testing:node:BenchLoopRaiseNode` — Bench Loop Raise — FROZEN: data node raising on odd input, for measuring a loop with failures.  _tags: benchmark, frozen, data, raise, loop_
- `haybale-testing:node:BenchSinkNode` — Bench Sink — FROZEN: control node with one data inlet, ending the branch.  _tags: benchmark, frozen, control, sink_
- `haybale-testing:node:CallbackEmitProbeNode` — Callback Emit Probe — Test version of EmitCallback — emits a callback to trigger event nodes  _tags: test, callback, emit, trigger, event_
- `haybale-testing:node:CallbackEventProbeNode` — Callback Event Probe — Test version of CustomCallback — listens for named callbacks  _tags: test, callback, listen, event, custom_
- `haybale-testing:node:CallbackRelayProbeNode` — Callback Relay Probe — Test-only: copies a callback inlet's value to its outlet on write, with a suffix.  _tags: test, callback, relay, loop_
- `haybale-testing:node:ChipFieldProbeNode` — Chip Field Probe — Hosts a chip select whose root is the select, beside a plain select  _tags: chips, select, widget, testing_
- `haybale-testing:node:ControlPayloadProbeNode` — Control Payload Probe — Test-only control node for exercising EXEC-edge payloads. Records the payload that arrived on its exec inlet, then advances — optionally writing its own payload, optionally forwarding the entered one implicitly (transparent conduit).  _tags: test, control, exec, payload, conduit_
- `haybale-testing:node:DisplayProbeNode` — Display Probe — Displays input values for debugging  _tags: display, debug, output, basic_
- `haybale-testing:node:DrainConsumerProbeNode` — Drain Consumer Probe — Test-only control node taking everything queued on its drain inlet, once per run  _tags: test, drain, consumer_
- `haybale-testing:node:DrainProducerProbeNode` — Drain Producer Probe — Test-only control node writing 0, 1, 2, ... to its outlet, one value per run  _tags: test, drain, producer_
- `haybale-testing:node:DynamicPortProbeNode` — Dynamic Port Probe —   _tags: testing, dynamic, push, pop, reconfigure_
- `haybale-testing:node:EdgeLinkProbeNode` — Edge Link Probe —   _tags: testing, edge, link, inlet, outlet, connection, adapter_
- `haybale-testing:node:EmptyFoldProbeNode` — Empty Fold Probe — Tests that a fold holding no ports raises  _tags: testing, fold_
- `haybale-testing:node:FoldProbeNode` — Fold Probe — Tests fold minting, lanes and open state  _tags: testing, fold, render_
- `haybale-testing:node:LongLabelProbeNode` — Long Label Probe — Hosts a status label far longer than the node is wide  _tags: label, status, widget, testing_
- `haybale-testing:node:MixedFoldProbeNode` — Mixed Fold Probe — Tests that a fold spanning two directions raises  _tags: testing, fold_
- `haybale-testing:node:NestedFoldProbeNode` — Nested Fold Probe — Tests that a fold declared inside another fold raises  _tags: testing, fold_
- `haybale-testing:node:PerformanceProbeNode` — Performance Probe — Helps test performance of execution system  _tags: performance, control, flow, event_
- `haybale-testing:node:PrintProbeNode` — Print Probe — Test version of Logger — logs a message and continues flow  _tags: test, print, log, message, terminal_
- `haybale-testing:node:RecordEmitProbeNode` — Record Emit Probe — Test control node emitting to every dataclass subscription in its pool  _tags: test, callback, emit, record_
- `haybale-testing:node:RecordEventProbeNode` — Record Event Probe — Test event node whose subscription is a dataclass callback value  _tags: test, callback, event, record_
- `haybale-testing:node:ReorderProbeNode` — Reorder Probe — Tests user-driven port ordering  _tags: testing, reorder, order_
- `haybale-testing:node:SettingsProbeNode` — Settings Probe — Test the Settings for debugging  _tags: settings, debug, test, example_
- `haybale-testing:node:SizeBoxAspectProbeNode` — Size Box Aspect Probe — Hosts an oversized widget declaring min_width only  _tags: size, resize, widget, testing_
- `haybale-testing:node:SizeBoxContentProbeNode` — Size Box Content Probe — Hosts an oversized widget with no declared box  _tags: size, resize, widget, testing_
- `haybale-testing:node:SizeBoxFixedProbeNode` — Size Box Fixed Probe — Hosts an oversized widget declaring both axes  _tags: size, resize, widget, testing_
- `haybale-testing:node:SwingletControlProbeNode` — Swinglet Control Probe — Test-only: a control node with an exec swinglet that counts its runs.  _tags: test, swinglet, control_
- `haybale-testing:node:SwingletEchoProbeNode` — Swinglet Echo Probe — Test-only: a data node whose float swinglet records an arrival and writes it plus one.  _tags: test, swinglet, on_change_
- `haybale-testing:node:SwingletPassProbeNode` — Swinglet Pass Probe — Test-only: a data node whose float swinglet records each run and writes ten times it.  _tags: test, swinglet_
- `haybale-testing:node:SwingletStopProbeNode` — Swinglet Stop Probe — Test-only: a data node whose float swinglet records each run and passes nothing on.  _tags: test, swinglet_
- `haybale-testing:node:SwingletVisualProbeNode` — Swinglet Visual Probe — Test-only: a data node with a swinglet on a drawn-only wire.  _tags: test, swinglet, visual_
- `haybale-testing:node:VisualProbeNode` — Visual Probe — Test-only: a data node with pins on a drawn-only wire.  _tags: test, visual, wire_
- `haybale-testing:node:WrappedLabelProbeNode` — Wrapped Label Probe — Hosts a long label that wraps onto more lines  _tags: label, wrap, widget, testing_

## type
- `haybale-testing:type:TEST_RECORD_CALLBACK` — Test Record Callback — Test callback subscription carried as a dataclass
- `haybale-testing:type:TEST_VISUAL` — Test Visual — Test-only: a text value on a drawn-only wire
- `haybale-testing:type:TEST_VISUAL_COUNT` — Test Visual Count — Test-only: a number on a drawn-only wire

## adapter
- `haybale-testing:adapter:BoolToIntAdapter` — BoolToIntAdapter — Convert bool to integer
- `haybale-testing:adapter:FloatToStringAdapter` — FloatToStringAdapter — Convert float to string
- `haybale-testing:adapter:IntToFloatAdapter` — IntToFloatAdapter — Convert integer to float

## widget
- `haybale-testing:widget:AspectBoxWidget` — AspectBoxWidget — Oversized content behind a declared width; height follows the content's aspect
- `haybale-testing:widget:ChipSelectRootWidget` — ChipSelectRootWidget — A chip select as the widget's root, declaring a width
- `haybale-testing:widget:FixedBoxWidget` — FixedBoxWidget — Oversized content behind a fully declared box
- `haybale-testing:widget:OversizedContentWidget` — OversizedContentWidget — Oversized content that sizes from its contents (no declared box)

## setting
- `haybale-testing:setting:TestingSettings` — Testing — 

## farmhand
- `haybale-testing:farmhand:affinity` — Affinity — Report handler thread and loop.
- `haybale-testing:farmhand:block` — Block — Sleep off-loop for `seconds`, or until `gate` is released.
- `haybale-testing:farmhand:echo` — Echo — Echo text back (canned read tool).
- `haybale-testing:farmhand:fail` — Fail — Always fails with a stable code.
- `haybale-testing:farmhand:release` — Release — Open a gate a Block call waits on.

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
