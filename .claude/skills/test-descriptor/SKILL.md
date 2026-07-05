---
name: test-descriptor
description: Explain the tests in a given test file (or test suite) as a concise one-line-per-test table. Use when the user asks to explain, summarize, list, or describe the tests in a file — pytest modules, JS/node:test files, or similar — one by one.
---

# Test Descriptor

## Goal

Turn a test file into a compact, scannable table: one row per test, stating what it verifies and
how (setup, action, assertion) in a single line. This is a read-and-summarize task, not a code
review — do not judge test quality or suggest fixes unless asked.

## Workflow

1. Read the full test file (and any fixture/helper files it imports if their setup is not obvious
   from usage alone — e.g. a shared fixture that mocks a non-trivial dependency).
2. Identify each individual test unit:
   - pytest: each `def test_*` function, and each parametrized case if `@pytest.mark.parametrize`
     produces meaningfully different scenarios worth distinguishing.
   - `node --test` / Jest / Mocha: each `test(...)`/`it(...)` block; group trivial `describe`
     blocks into the table rather than adding a row for the `describe` itself.
   - Other frameworks: use their smallest independently-runnable unit.
3. For each test, determine:
   - **Setup**: the state it arranges (mocks, fixtures, pre-existing files/state, monkeypatches).
   - **Action**: what it invokes (the function/CLI/endpoint under test, with key args if they
     drive the behavior being tested).
   - **Assertion**: what it actually checks — the specific behavior, not just "it passes".
4. Compress each test into one line: what it verifies, phrased so a reader who has never opened
   the file understands the behavior under test without needing to read the code.
5. Preserve file order — do not alphabetize or group unless the user asks for grouping.
6. If a test's name and body diverge (e.g. name says "skips" but assertion checks something else
   too), describe what the assertions actually check, not just the name.

## Output Shape

Default to a markdown table:

```markdown
| # | Test | Description |
|---|------|-------------|
| 1 | `test_name_one` | One line: setup context + what behavior is verified. |
| 2 | `test_name_two` | One line: setup context + what behavior is verified. |
```

Rules:
- Use the exact test function/block name in the Test column (as inline code), not a paraphrase.
- Keep each Description to a single sentence. If a test genuinely needs two clauses (e.g. an
  unusual setup plus a non-obvious assertion), use one sentence with a semicolon or em dash —
  never wrap to multiple lines in the cell.
- Number rows sequentially in file order.
- Do not add rows for helper functions, fixtures, or module-level setup — only actual test units.
- If the file is large enough that fixtures materially change what a test does, mention the
  fixture inline only when it isn't obvious from the test name/args.

## When Asked for More Than a Table

If the user asks for narrative explanation instead of (or in addition to) the table, expand each
row into 2-3 sentences covering: why the test exists (what regression/behavior it guards),
setup, and the specific assertion — but still preserve one-test-per-section structure so it stays
scannable.
