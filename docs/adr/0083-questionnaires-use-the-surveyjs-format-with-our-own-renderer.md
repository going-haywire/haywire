---
name: questionnaires-use-the-surveyjs-format-with-our-own-renderer
description: A Questionnaire is written in a subset of SurveyJS JSON plus a check element, validated on post and drawn by the studio's own NiceGUI renderer; the SurveyJS library itself is not used
status: accepted
level: architectural
---

# Questionnaires use the SurveyJS format with our own renderer

**Context.**

- An agent posts a Questionnaire through Farmhand for the user to answer in the studio during a live check, and reads the Findings back. The agent writes the format; the agent reads the answers.
- SurveyJS is the most widely used JSON questionnaire format, so agents write it fluently: a small model, given no hint of a subset, wrote a 22-check live check entirely in common types and simple `visibleIf` conditions.
- The SurveyJS library (`survey-core`, MIT) would render it, but it is a JS bundle to vendor and theme, its look does not come from the design guide, and its in-progress state is lost on every editor redraw unless synced by hand.
- A live check is mostly do / expect / verdict items; in plain SurveyJS each takes four elements (about 1.2 KB), and the renderer cannot tell it from any other radio group.

**Decision.**

- **The format is SurveyJS JSON, a subset**: the types `boolean`, `radiogroup`, `checkbox`, `dropdown`, `text`, `comment`, `rating`, `ranking`, `html`, `panel` and `pages`, and `visibleIf` / `enableIf` / `requiredIf` with a small grammar (references, comparisons, `and / or / not`, `empty / notempty`, `contains / anyof`). No functions, calculated values, piping, triggers, matrices or dynamic panels.
- **Plus one element of our own, `check`** (`do`, `expect`; answered with a verdict and a note), so live checks stay compact and the editor can count what failed.
- **The studio draws it with its own NiceGUI renderer** built from `hui` elements. No SurveyJS code runs; `html` is sanitized.
- **`post_questionnaire` rejects anything outside the subset**, naming the element and property, so the boundary is taught by the error rather than by a form that silently drops things.
- **Answers keep SurveyJS's shape** (question name → value), `check` answers being `{verdict, note}`.

**Considered.**

- *The SurveyJS library in the page or a sandboxed iframe.* Every question type and the full expression language for free, at the cost of a vendored bundle, a foreign look and redraw-safe state glue.
- *Agent-written HTML and JavaScript behind a `postMessage` bridge.* The most freedom, but every questionnaire is a small program that can break, costs many tokens, and returns answers in a shape of its own.
- *A schema of our own.* Exactly what we need, but one no agent has seen before.

**Consequences.**

- The subset, the `check` element and the grammar are a contract with agents: the canon page, the validator and the renderer change together.
- A SurveyJS feature outside the subset is added by extending all three, never by passing it through.
- `check` is not SurveyJS; a questionnaire using it does not open in SurveyJS tools.
