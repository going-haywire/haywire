---
status: draft
doc_template: reference
scope: The Questionnaire format (a SurveyJS subset plus the check element), the exchange between agent and user, and the Findings an agent reads back
see-also:
  - glossary.md
  - ../adr/0083-questionnaires-use-the-surveyjs-format-with-our-own-renderer.md
  - ../architecture/studio/studio-arch.md
---

# Questionnaire

A **Questionnaire** is how an agent asks the user to check something in the running studio
and gets the answers back in a structured form. The agent posts it through Farmhand, the
user works through it in the studio's ASIDE slot, and the agent reads the **Findings**.

The format is [SurveyJS](https://surveyjs.io/form-library/documentation/design-survey/create-a-simple-survey)
JSON, restricted to the subset below, plus one element of Haywire's own, `check`. The
studio draws it with its own renderer; no SurveyJS code runs. Anything outside the subset
is rejected when it is posted, with an error that names the element and the property
([ADR 0083](../adr/0083-questionnaires-use-the-surveyjs-format-with-our-own-renderer.md)).

## The exchange

1. The agent calls `haybale-studio_post_questionnaire` with the Questionnaire. It replaces the one
   on show; earlier ones stay on disk under `~/.haywire/db/haybale_studio/questionnaires/`.
2. The post opens the *Questionnaire* tab in the aside of every open studio session,
   opening the aside if it is closed, and the agent tells the user it is there. The tab
   counts the unanswered questions; while ASIDE is closed, the tab and its count show next
   to the aside toggle at the right of the top bar. The user can close the tab at any time:
   the Questionnaire and its answers stay, and the next post opens the tab again.
3. The user answers. Each answer is stored as it is given and appears in every open
   studio session. *Submit* requires the required questions; *Submit anyway* does not.
   After submitting, the form is read-only, and the answers of questions hidden by a
   condition are dropped.
4. When the user says they are done, the agent calls `haybale-studio_get_findings`. `status` says
   whether the Questionnaire was submitted; an open one returns the answers so far.
   Reading a submitted Questionnaire takes it out of the studio (`closed: "read"`).
5. *Discard* takes it out of the studio at any time (`closed: "discarded"`). A closed
   Questionnaire takes no more answers; its Findings stay readable until the next post.

Posting, answering and discarding need the edit tier; reading the Findings needs the view
tier. There is no push to the agent: it asks for the Findings when
the user says so.

## Top level

| Property | Meaning |
|---|---|
| `title` | Shown above the form, and part of the Questionnaire's id. |
| `description` | Shown under the title. |
| `pages` | A list of pages. Give either `pages` or `elements`. |
| `elements` | The elements of a one-page Questionnaire. |
| `showProgressBar` | Any value but `"off"` shows a progress bar over a multi-page form. |
| `showQuestionNumbers` | `"off"` hides the question numbers. |
| `completedHtml` | HTML shown once the Questionnaire is submitted. |

A page takes `name`, `title`, `description`, `elements` and `visibleIf`. *Next* moves to the
next visible page once that page's required questions are answered.

## Elements

Every question takes `type`, `name` (unique; answers are keyed by it), `title`,
`description`, `isRequired`, `visibleIf`, `enableIf` and `requiredIf`, plus the properties
of its type:

| `type` | Extra properties | Answer |
|---|---|---|
| `check` | `do`, `expect` (both required) | `{"verdict": "pass" \| "fail" \| "blocked" \| "skip", "note": "…"}`; `note` only on fail or blocked |
| `boolean` | `labelTrue`, `labelFalse` | `true` / `false` |
| `radiogroup` | `choices`, `colCount`, `showOtherItem`, `otherText` | the chosen value |
| `checkbox` | `choices`, `colCount`, `showOtherItem`, `otherText` | a list of chosen values |
| `dropdown` | `choices`, `placeholder` | the chosen value |
| `text` | `inputType` (`text`, `number`, `date`, `color`, `range`, `email`, `url`), `placeholder`, `min`, `max`, `step` | the text, or a number for `number` and `range` |
| `comment` | `placeholder`, `rows` | the text |
| `rating` | `rateMin`, `rateMax` (at most 20 apart), `rateStep`, `rateType` (`labels` or `stars`), `minRateDescription`, `maxRateDescription` | the number |
| `ranking` | `choices` | the values in the user's order |

Two elements take no answer:

| `type` | Properties |
|---|---|
| `html` | `html` (sanitized before it is shown), `name`, `visibleIf` |
| `panel` | `name`, `title`, `description`, `elements`, `state` (`default`, `expanded`, `collapsed`), `visibleIf`, `enableIf` |

A choice is a string, a number, or `{"value": …, "text": "…"}`. With `showOtherItem`, the
choice `"other"` is added, and the text the user types goes under `"<name>-Comment"`.

Use a `check` for each *do this, expect that* step of a live check: it takes one element
where plain SurveyJS needs four, and the Findings list the failed and blocked ones.

## Conditions

`visibleIf`, `enableIf` and `requiredIf` hold an expression:

| Form | Example |
|---|---|
| Reference | `{name}`; a `check`'s value is its verdict |
| Literal | `3`, `'text'`, `"text"`, `true`, `false`, `['a', 'b']` |
| Comparison | `{q} = 'yes'` (also `==`), `!=` (also `<>`), `<`, `>`, `<=`, `>=` |
| Logic | `and` (`&&`), `or` (`||`), `not` (`!`), parentheses |
| Tests | `{q} empty`, `{q} notempty`, `{q} contains 'x'`, `{q} notcontains 'x'`, `{q} anyof ['a', 'b']` |

Text compares without regard to case, and a number in text compares as a number. A
comparison with an unanswered question is false, except `!=`. Every reference must name a
question. Functions (`iif`, `age`, …), arithmetic, calculated values and piping are not
supported.

## Not supported

Matrices, dynamic panels, file upload, `expression` questions, triggers, calculated values,
piping, custom widgets, and every presentation property not listed above (`logoPosition`,
`widthMode`, `progressBarType`, …). The post is rejected with the list of what to remove.

## Findings

`haybale-studio_get_findings` returns:

| Field | Meaning |
|---|---|
| `id`, `title` | The Questionnaire. |
| `status` | `"open"` or `"submitted"`. |
| `incomplete` | Submitted with visible questions unanswered. |
| `answers` | Question name → answer, in the shapes above. |
| `unanswered` | Names of the visible questions without an answer. |
| `failed_checks` | Names of the checks answered `fail` or `blocked`. |
| `posted_at`, `posted_by`, `submitted_at`, `submitted_by` | When and by whom, in UTC; the principal is `null` when authentication is off. |
| `user_agent` | The submitting browser. |
| `closed`, `closed_at`, `closed_by` | `"read"` once an agent read the submitted Findings, `"discarded"` when a user discarded it, `null` while it is on show; when and by whom. |
| `ledger_seq` | The error ledger's cursor when posted, when submitted, and now. Pass `posted` as `since_seq` to `haybale-studio_get_errors` for the errors logged during the check. |

## Example

```json
{
  "title": "Divider resize",
  "pages": [
    {
      "elements": [
        {
          "type": "check",
          "name": "drag",
          "title": "Drag resizes ASIDE",
          "do": "Open the aside with the top-bar toggle, then drag its left edge to the left.",
          "expect": "The aside grows and the canvas shrinks.",
          "isRequired": true
        },
        {
          "type": "comment",
          "name": "drag_detail",
          "title": "Where did it stop?",
          "visibleIf": "{drag} = 'fail'"
        },
        {
          "type": "rating",
          "name": "feel",
          "title": "How smooth was it?",
          "rateMin": 1,
          "rateMax": 5,
          "minRateDescription": "jerky",
          "maxRateDescription": "smooth"
        }
      ]
    }
  ]
}
```
