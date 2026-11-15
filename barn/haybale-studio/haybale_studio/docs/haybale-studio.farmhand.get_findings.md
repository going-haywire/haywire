# Get findings

`haybale-studio:farmhand:get_findings` · kind: farmhand

Read the user's answers to the current Questionnaire.

## Agent Instructions

Read the Findings of the current Questionnaire: status ('open' or 'submitted'), incomplete, answers by question name (a check's answer is {verdict, note}), the unanswered questions, the failed or blocked checks, who posted and submitted it and when, the browser user agent, and ledger_seq (posted / submitted / now): pass ledger_seq.posted as since_seq to haybale-studio_get_errors for the errors logged during the check. Answers are stored as they are given, so an open questionnaire returns the answers so far.

## Details

- **input_schema**: `{'type': 'object', 'properties': {}, 'required': []}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
