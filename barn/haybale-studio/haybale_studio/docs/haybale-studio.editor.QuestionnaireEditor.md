# Questionnaire

`haybale-studio:editor:QuestionnaireEditor` · kind: editor

The Questionnaire an agent posted for a live check. Answer it, then submit.

## Details

- **default_slot**: `aside`
- **opens**: `OpenBehavior.REQUIRED`
- **order**: `100`

## Notes

Shows the Questionnaire an agent posted, so the user can work through it and submit.

An agent posts it with the `post_questionnaire` tool and reads the answers
back with `get_findings`. Answering needs the edit tier; a viewer sees the
form read-only. After *Submit* the form is read-only for everyone.
