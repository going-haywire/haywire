# Questionnaire

`haybale-studio:state:QuestionnaireState` · kind: state

The Questionnaire an agent posted for a live check, its answers and its status

## Notes

Holds the current Questionnaire and stores every change under the library's storage folder.

One Questionnaire is current at a time; a new post replaces it, and earlier
ones stay on disk under `questionnaires/`. It leaves the studio when an agent
reads its submitted Findings, or when a user discards it; its Findings stay
readable until the next post. Every change reaches every open studio session.

```python
q = state.post(definition, principal="agent")
state.set_answer("login", {"verdict": "fail", "note": "button greyed out"})
state.submit(principal="tester", user_agent="Firefox", anyway=True)
state.findings()  # {"id": ..., "status": "submitted", "answers": {...}, ...}
state.close("read", principal="agent")  # leaves the studio
```
