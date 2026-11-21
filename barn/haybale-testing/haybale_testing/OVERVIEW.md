# Testing

Test library for test support

## Nodes
### Testing
- **Add Float Probe** — Test arithmetic node — adds two float values
- **Add Port Probe** — 
- **Array Callback Probe** — Test-only: an array-of-CALLBACK outlet and inlet.
- **Array Exec Probe** — Test-only: an array-of-EXEC outlet and inlet on a control node.
- **Begin Play Probe** — Test version of BeginPlay — triggered once when execution starts
- **Bench Bare** — FROZEN: minimal no-port control node for measuring _execute dispatch overhead.
- **Bench Data Pass** — FROZEN: data node passing x + 1 on, for measuring data-flow evaluation.
- **Bench Data Raise** — FROZEN: data node whose worker always raises, for measuring the failure path.
- **Bench Exec** — FROZEN: minimal EXEC in→out conduit for measuring control-edge payload forwarding.
- **Bench Fan In** — FROZEN: data node adding two inputs, for measuring a fan-in in data-flow evaluation.
- **Bench Loop Raise** — FROZEN: data node raising on odd input, for measuring a loop with failures.
- **Bench Sink** — FROZEN: control node with one data inlet, ending the branch.
- **Callback Emit Probe** — Test version of EmitCallback — emits a callback to trigger event nodes
- **Callback Event Probe** — Test version of CustomCallback — listens for named callbacks
- **Callback Relay Probe** — Test-only: copies a callback inlet's value to its outlet on write, with a suffix.
- **Control Payload Probe** — Test-only control node for exercising EXEC-edge payloads. Records the payload that arrived on its exec inlet, then advances — optionally writing its own payload, optionally forwarding the entered one implicitly (transparent conduit).
- **Display Probe** — Displays input values for debugging
- **Drain Consumer Probe** — Test-only control node taking everything queued on its drain inlet, once per run
- **Drain Producer Probe** — Test-only control node writing 0, 1, 2, ... to its outlet, one value per run
- **Dynamic Port Probe** — 
- **Edge Link Probe** — 
- **Empty Fold Probe** — Tests that a fold holding no ports raises
- **Fold Probe** — Tests fold minting, lanes and open state
- **Mixed Fold Probe** — Tests that a fold spanning two directions raises
- **Nested Fold Probe** — Tests that a fold declared inside another fold raises
- **Performance Probe** — Helps test performance of execution system
- **Print Probe** — Test version of Logger — logs a message and continues flow
- **Record Emit Probe** — Test control node emitting to every dataclass subscription in its pool
- **Record Event Probe** — Test event node whose subscription is a dataclass callback value
- **Reorder Probe** — Tests user-driven port ordering
- **Settings Probe** — Test the Settings for debugging
- **Size Box Aspect Probe** — Hosts an oversized widget declaring min_width only
- **Size Box Content Probe** — Hosts an oversized widget with no declared box
- **Size Box Fixed Probe** — Hosts an oversized widget declaring both axes
- **Swinglet Control Probe** — Test-only: a control node with an exec swinglet that counts its runs.
- **Swinglet Echo Probe** — Test-only: a data node whose float swinglet records an arrival and writes it plus one.
- **Swinglet Pass Probe** — Test-only: a data node whose float swinglet records each run and writes ten times it.
- **Swinglet Stop Probe** — Test-only: a data node whose float swinglet records each run and passes nothing on.
- **Swinglet Visual Probe** — Test-only: a data node with a swinglet on a drawn-only wire.
- **Visual Probe** — Test-only: a data node with pins on a drawn-only wire.

## Types
- **Test Record Callback** — Test callback subscription carried as a dataclass
- **Test Visual** — Test-only: a text value on a drawn-only wire
- **Test Visual Count** — Test-only: a number on a drawn-only wire

## Adapters
- **BoolToIntAdapter** — Convert bool to integer
- **FloatToStringAdapter** — Convert float to string
- **IntToFloatAdapter** — Convert integer to float

## Widgets
- **AspectBoxWidget** — Oversized content behind a declared width; height follows the content's aspect
- **FixedBoxWidget** — Oversized content behind a fully declared box
- **OversizedContentWidget** — Oversized content that sizes from its contents (no declared box)

## Settings
- **Testing** — 

## Farmhands
- **Affinity** — Report handler thread and loop.
- **Block** — Sleep off-loop for `seconds`, or until `gate` is released.
- **Echo** — Echo text back (canned read tool).
- **Fail** — Always fails with a stable code.
- **Release** — Open a gate a Block call waits on.

## States
- **Test Session State** — 

## Panels
- **Connection Errors** — 
- **Connection Path** — 
- **Connection Warnings** — 
- **Copy Node** — 
- **Copy Selection** — 
- **Create Node** — 
- **Delete Connection** — 
- **Delete Node** — 
- **Inspect Connection** — 
- **Paste** — 
- **Redraw Node** — 
- **Reset Node** — 
- **Revalidate Node** — 
- **Test SessionState Panel** — 

## Themes
- **Test Light** —
