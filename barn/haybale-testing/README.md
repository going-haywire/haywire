# Testing

<!-- marketstall:share-url:start -->
*Subscribe URL not yet published — run `haywire share --save`.*
<!-- marketstall:share-url:end -->

Test library for test support

## Nodes
### Testing
- **Bench Bare Node** — FROZEN: minimal no-port control node for measuring _execute dispatch overhead.
- **Bench Exec Node** — FROZEN: minimal EXEC in→out conduit for measuring control-edge payload forwarding.
- **Control Payload TestNode** — Test-only control node for exercising EXEC-edge payloads. Records the payload that arrived on its exec inlet, then advances — optionally writing its own payload, optionally forwarding the entered one implicitly (transparent conduit).
- **Display** — Displays input values for debugging
- **Dynamic Port TestNode** — 
- **Edge Link TestNode** — 
- **Group And Sections** — Tests Rendering for Group and Sections
- **Performance Testing Node** — Helps test performance of execution system
- **Settings Test Node** — Test the Settings for debugging
- **Size Box (content-sized)** — Hosts an oversized widget with no declared box
- **Size Box (declared box)** — Hosts an oversized widget declaring both axes
- **Size Box (declared width)** — Hosts an oversized widget declaring min_width only
- **Test Add Float** — Test arithmetic node — adds two float values
- **Test Begin Play** — Test version of BeginPlay — triggered once when execution starts
- **Test Custom Callback** — Test version of CustomCallback — listens for named callbacks
- **Test Emit Callback** — Test version of EmitCallback — emits a callback to trigger event nodes
- **Test Print** — Test version of Logger — logs a message and continues flow

## Types
- **Boolean** — True or False
- **Float** — Decimal numberer
- **Integer** — Whole number
- **String** — Text data
- **Temperature** — Temperature in Celsius

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
- **Block** — Sleep off-loop for `seconds`.
- **Echo** — Echo text back (canned read tool).
- **Fail** — Always fails with a stable code.

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
