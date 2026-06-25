---
name: graph-first-reasoning
description: Convert a messy, unclear, diagnostic, dependency-tracing, planning, debugging, or "what should I do?" problem into a small reasoning graph before answering. Use when graphing concrete entities, relationships, blockers, or next actions would make the answer clearer; avoid when a direct answer would be simpler and no graph adds value.
---

# Graph-First Reasoning

Use this skill to expose the smallest useful structure behind a problem, then give the smallest useful action. The goal is not to make the answer look complex; the goal is to clarify entities, relationships, blocked paths, and next steps.

## Workflow

1. Decide whether a graph makes the answer clearer.
   - Use it for debugging, decision problems, unclear goals, small task planning, technical diagnosis, dependency tracing, and simple "what should I do?" questions.
   - Do not use it when a direct answer is clearer and no graph adds value.
2. Build the least number of concrete nodes needed.
   - Small tasks: 3-8 nodes.
   - Medium tasks: 8-15 nodes.
   - Large tasks: up to 15-50 nodes only when necessary.
3. Add only edges that explain dependency, cause, blockage, sequence, intent, or action.
4. Identify the key path through the graph.
5. Give the smallest useful next action.
6. Before finalizing, simplify anything that does not clarify the answer.
7. When the user wants saved graph artifacts, write the final graph text to a temporary file and run `scripts/render_graph.py --name <name> <file>`. This creates `docs/graph/graph_<name>.md`, `docs/graph/graph_<name>.mmd`, and `docs/graph/graph_<name>.png`.
   - Use `--output-dir <dir>` when the user asks for a different destination.
   - Use `--no-png` only when PNG rendering is explicitly unnecessary.

## Graph Rules

- Use everyday labels, not academic, corporate, or enterprise labels.
- Do not over-abstract simple problems.
- Do not add constraints unless stated or strongly implied.
- Mark missing information only when it changes the next action.
- Mention uncertainty only when it changes the next action.
- Avoid graph cosplay: no fancy labels, no inflated relations, and no graph elements that do not improve the answer.

## Node Names

Use short, readable tag names:

```text
user
file
browser
request
backend
error
text_editor
document
```

Avoid abstract or inflated names:

```text
HumanIntentActor
AcquisitionMeansLayer
ProtocolHandshakePhase
ResourceFulfillmentSubsystem
```

## Edge Names

Use simple relations:

```text
user --wants--> ice_cream
browser --requests--> website
request --hits--> backend
backend --returns--> error
missing_header --causes--> rejection
```

Avoid inflated relations:

```text
user --interfaces_with_operational_context--> system
request --transits_through_protocol_integrity_layer--> response
```

## Output

When using this skill, output exactly these sections:

```text
NODES:

* tagname = description

EDGES:

* tagname --relation_or_intent--> tagname

KEY PATH:

* tag -> tag -> tag

ACTION:

* smallest useful next action

ANSWER:

* concise answer
```

## Examples

User problem: Upload fails with HTTP 400: missing content-type.

```text
NODES:

* upload = user action
* file = selected file
* request = frontend API request
* backend = upload endpoint
* error = HTTP 400 missing content-type
* content_type = required request header or body format

EDGES:

* upload --sends--> file
* file --goes_in--> request
* request --hits--> backend
* backend --returns--> error
* error --points_to--> content_type

KEY PATH:

* request -> backend -> error -> content_type

ACTION:

* Inspect the request construction and verify that the correct Content-Type or body format is sent.

ANSWER:

* The likely broken point is the frontend request format. Check whether the upload sends the expected Content-Type header or multipart/form-data body.
```

User problem: Create a text document on Windows 10.

```text
NODES:

* user = person wanting to create a text document
* windows = Windows 10 operating system
* notepad = built-in plain text editor
* document = saved text file

EDGES:

* user --uses--> windows
* windows --provides--> notepad
* notepad --creates--> document

KEY PATH:

* user -> windows -> notepad -> document

ACTION:

* Open Notepad, write the text, then save the file.

ANSWER:

* Use the Start menu, open Notepad, write your text, then use File > Save As to save the document.
```
