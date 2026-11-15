"""Shift the line-range snippet embeds in docs/ to follow files changed since a base ref.

Run from the repo root after a change that moves lines in embedded files, with
docs/ as it is on the base ref (the ranges are read from the working copy and
mapped through the diff of each file against the base):

    python3 workbench/playground/shift_doc_snippets.py origin/master

A range that starts or ends inside a changed block is moved to that block's
new start or end; read those once.
"""
import difflib, pathlib, re, subprocess, sys
base = sys.argv[1]
changed = set(subprocess.run(["git", "diff", "--name-only", base], capture_output=True, text=True).stdout.split())
pat = re.compile(r'(--8<-- ")([^":]+):(\d+):(\d+)(")')
for doc in pathlib.Path("docs").rglob("*.md"):
    if "adr" in doc.parts or "superpowers" in doc.parts: continue
    text = doc.read_text()
    def fix(m):
        f, a, b = m[2], int(m[3]), int(m[4])
        if f not in changed: return m[0]
        old = subprocess.run(["git", "show", f"{base}:{f}"], capture_output=True, text=True).stdout.split("\n")
        new = pathlib.Path(f).read_text().split("\n")
        ops = difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
        def at(i, start):
            for tag, i1, i2, j1, j2 in ops:
                if i1 <= i < i2:
                    if tag == "equal": return j1 + (i - i1)
                    return j1 if start else max(j1, j2 - 1)
            return None
        na = at(a - 1, True)
        nb = at(min(b, len(old)) - 1, False)
        if na is None or nb is None: print("UNMAPPED", doc, m[0]); return m[0]
        if (na + 1, nb + 1) != (a, b): print(f"{doc}: {f}:{a}:{b} -> {na+1}:{nb+1}")
        return f"{m[1]}{f}:{na+1}:{nb+1}{m[5]}"
    new_text = pat.sub(fix, text)
    if new_text != text: doc.write_text(new_text)
