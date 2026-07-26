# App settings

Machine-wide options shared by every project, stored at
**`~/.prepare_lora_kit/settings.yaml`** (`prepare_lora_kit.paths.SETTINGS_PATH`). Opened from the
**Settings** button in either appbar.

The file lives outside the checkout so it survives a re-clone and is shared by every working copy.
Absent, empty and partial files all resolve to a fully defaulted document: settings are strictly
additive, and the app behaves exactly as it did before this feature existed until something is
configured.

## Two mechanisms, and every field is exactly one of them

**(a) Seeded at project creation.** Copied into a new project's YAML once, by
`settings/seeding.py`, from the single creation choke point `project_registry.default_project_data`.
Existing projects are never touched, so a run always does exactly what its own YAML says. Change a
global later and nothing that already exists moves.

**(b) Machine fallback behind an existing null.** For fields that *already* defaulted to `None`
meaning "app default", the setting replaces a hard-coded constant. No YAML changes meaning — `null`
meant "app default" before and still does — and a project that names a value still wins.

| Setting | Mechanism | Lands in / replaces |
|---|---|---|
| `hardware.vram_tier` | a | `CaptionBboxStep.vram_tier` **and** `CaptionVerifierStep.vram_tier` |
| `project_defaults.caption_model_id` / `caption_model_task` | a | `CaptionBboxStep` |
| `project_defaults.t2i_model_id` | a | `CaptionVerifierStep` |
| `project_defaults.vae_model_id` | a | `VaeGateStep` |
| `project_defaults.coverage_embedding_model` | a | `CurateStep` |
| `project_defaults.seedvr2_dit_model` | a | `UpscaleStep` |
| `project_defaults.caption_model_type` | a | `AuditStep` |
| `hardware.cuda_device` | b | `UpscaleConfig.seedvr2_cuda_device is None` → device 0 |
| `hardware.seedvr2_submodule_dir` | b | `seedvr2_adapter.default_seedvr2_submodule_dir()` |
| `hardware.seedvr2_model_dir` | b | `seedvr2_adapter.DEFAULT_SEEDVR2_MODEL_DIR` |
| `huggingface.home` | b | not a project field — `HF_HOME` |

`vram_tier` is one machine fact seeding two steps: a user with a 16 GB card should not have to say
so twice.

The SeedVR2 directories and CUDA device are deliberately **not** seeded. They are absent from the
curated UI field schema, and baking a machine path into every project YAML would go stale the
moment the checkpoint cache moves.

## `null` is the only "unset"

Every field is optional and defaults to `None`, which always means *"not configured — use the app
default"*. Seeding skips `None` fields entirely, so a default settings file produces byte-identical
project YAML to what the app wrote before settings existed — asserted by
`test_default_settings_reproduce_todays_pipeline_exactly`. The modal shows the real app default as
placeholder text, so an empty box reads as "using X" rather than "missing".

Parsing is forgiving in one direction only. Unknown keys and blank strings are dropped on the way in
(a file from a newer build must not break an older one), but a *known* key holding an invalid value
raises, so a typo surfaces in the modal instead of silently reverting.

## Hugging Face

**No token is ever stored by this app.** `huggingface_hub.get_token()` already resolves the
`HF_TOKEN` environment variable and the token file the CLI writes, so reusing it means there is
exactly one place a credential lives and we are not another one.

`hf auth login` is the command to show. `huggingface-cli` was removed in huggingface_hub 1.0 — its
entry point now only prints a deprecation notice and exits — so `hub.login_command()` probes for the
`hf` binary and only falls back to the old name when the modern one genuinely is not installed.

Three things the modal offers, all button-driven:

- **Check login** → `whoami()`.
- **Check model access** → `auth_check(repo_id)` per configured model, mapped to
  `ok` / `gated` / `unauthorized` / `missing` / `offline`. It checks the ids **currently on screen**,
  so trying out a model id does not require saving first. The gated FLUX.2 klein VAE default is
  always included, because it is the one that actually bites.
- **Detect** → VRAM probe, suggesting a tier.

There is no automatic per-run preflight: it would add a network round-trip to every run and break
offline use. Instead, failures are translated where they happen.

### Readable failures

`hub.hub_error_context(model_id)` wraps every model-load site
(`caption_bbox/vlm.py`, `caption_verifier/loader.py`, `vae_gate/vae.py`, `embedding/loaders.py`,
`utils/image.py`). A gated repo otherwise surfaces deep inside diffusers/transformers as a bare 401,
which reads as "the model is broken" rather than "you need to accept a licence":

```
401 Client Error. ...

'black-forest-labs/FLUX.2-klein-base-9B' is a gated repository and this machine
has not been granted access.
  1. Run `hf auth login`
  2. Accept the licence at https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9B
  3. Re-run this step.
```

Two rules it must keep:

- **Anything that is not a Hub access error passes through untouched**, `CancelledRun` included.
- **Hub errors are extended via their own `append_to_message`, never rebuilt.**
  `HfHubHTTPError.__init__` takes a required keyword `response`, so reconstructing one from a message
  alone raises `TypeError` and would replace the real failure with a bug in the helper.

`vlm.py` additionally stops trying further adapter classes once it sees an access error — a gated
repo will not become available on the next `AutoModel*` class, and retrying only buries the message
under four copies of the same 401.

## `HF_HOME` applies at startup only

`store.apply_environment()` runs from the Click group callback in `cli/_shared.py`, before any
command executes and therefore before any step lazily imports `huggingface_hub` — which resolves
`HF_HOME` once, at import time. Calling it later is a silent no-op, which is why the field is
labelled "takes effect after restarting the app". It uses `os.environ.setdefault`, so an `HF_HOME`
exported in the shell outranks the stored one.

## Bridge

| method | network / torch? | notes |
|---|---|---|
| `get_settings()` | **no** | settings + choices + placeholders |
| `save_settings(payload)` | no | validates, then writes atomically |
| `hf_status()` | network | button-driven |
| `check_model_access(repo_ids)` | network | button-driven |
| `detect_hardware()` | imports torch | button-driven |

**`get_settings` is pure disk plus torch-free catalogs.** The modal has to open instantly, so
everything slow sits behind its own button — probing VRAM would drag `torch` into the UI process and
stall it for seconds. `test_get_settings_does_not_import_torch` guards this.

Dropdown options come from the existing catalogs rather than hand-typed lists — the caption-model
list is read straight off `config_schema/steps/caption_bbox.FIELDS`, so the Settings dropdown and the
step-config dropdown cannot diverge.

The Settings modal is opened by a button and must stay out of
`job/controller.js:handlePendingInput`; it must not use `modalCancelButton`, which cancels a *run*.

## Tests

`tests/settings/` plus `tests/ui/dev/settings/` and `tests/ui/static/settings.test.js`.

> The autouse `isolated_settings` fixture in `tests/conftest.py` is a safety rail, not a
> convenience. Without it every test that creates a project would read the developer's real
> `~/.prepare_lora_kit/settings.yaml`, and any test that saved settings would overwrite it.

`tests/settings/test_hub.py` uses the real `huggingface_hub` error classes (skipping if the package
is absent) rather than fakes, because the `response=` keyword constraint is exactly what these tests
exist to pin down. No test touches the network — `auth_check` is always stubbed.
