# Post questionnaire

`haybale-studio:farmhand:post_questionnaire` · kind: farmhand

Post a Questionnaire for the user to answer in the studio's ASIDE slot.

## Agent Instructions

Post a Questionnaire (SurveyJS JSON, a subset) for the user to work through in the studio during a live check; it replaces the current one. Types: boolean, radiogroup, checkbox, dropdown, text (inputType text/number/date/color/range/email/url), comment, rating, ranking, html, panel, plus check {type:'check', name, title, do, expect}, answered with a verdict (pass/fail/blocked/skip) and a note: prefer check for each do/expect step. Use 'pages' or top-level 'elements'. Conditions visibleIf/enableIf/requiredIf: {name}, = != < > <= >=, and/or/not, empty/notempty, contains/anyof; a check's value is its verdict. No functions, calculated values, piping, triggers or matrices. Anything else is rejected. Full format: farmhand://docs/reference/questionnaire.md. After posting, tell the user a questionnaire waits in the studio's aside, then call haybale-studio_get_findings when they say they are done.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'questionnaire': {'anyOf': [{'type': 'object'}, {'type': 'string'}]}}, 'required': ['questionnaire']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
