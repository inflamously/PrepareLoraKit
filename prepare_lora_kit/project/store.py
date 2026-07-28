"""The on-disk shape of a project: one folder, one file per pipeline step.

A project lives at ``~/.prepare_lora_kit/projects/<name>/`` — outside the
checkout, for the same reason ``settings.yaml`` does (it survives a re-clone and
is shared by every working copy), and because dataset paths are machine-specific
user data that has no business in a repo.

    demo/
      index.yaml            name, input/output dirs, and which steps run
      caption_bbox.yaml     one file per step: its substeps and its settings
      ...

**Slugs are the on-disk vocabulary; CamelCase step types are the in-memory one.**
The translation happens in exactly two functions here, :func:`read_project_folder`
and :func:`write_project_folder`. Everything downstream — ``RunState`` keys,
``reports/<StepType>_report.json``, ``STEP_INVOKE_MAP``, ``SUBSTEP_REGISTRY``,
``CONFIG_FIELD_SCHEMA``, the UI's ``StepPayload.type`` — stays CamelCase. Keeping
that line sharp is what stops a file-layout change from reaching the engine.

:func:`read_project_folder` returns the same flat dict shape the single-file YAML
used to parse into, so ``ProjectConfig`` builds itself from a folder exactly as it
did from a file.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from prepare_lora_kit import paths
from prepare_lora_kit.pipeline.configuration import (
    step_slug,
    step_slugs,
    step_type_for_slug,
)
from prepare_lora_kit.project.pipeline.substeps import substep_ids_for
from prepare_lora_kit.project.yaml_style import ProjectDumper, inline
from prepare_lora_kit.utils.atomic_yaml import write_yaml_atomic

INDEX_FILENAME = "index.yaml"

# A project name becomes a directory name, so this is the boundary that keeps a
# name out of a parent directory or an absolute path. Everything destructive in
# project_registry works from a name that has been through dir_name_for.
_SAFE_NAME = re.compile(r"[A-Za-z0-9._-]+")

_TMP_SUFFIX = ".plk_tmp"
_OLD_SUFFIX = ".plk_old"


# ── locations ─────────────────────────────────────────────────────────────────

def projects_dir() -> Path:
    """The active projects root.

    Read through the module attribute (not a from-import) so that redirecting
    ``paths.PROJECTS_DIR`` in a test is honored here. A from-import would bind at
    import time and quietly point the whole suite at the developer's real
    project library — which these writers create, rename and delete.
    """
    return Path(paths.PROJECTS_DIR)


def dir_name_for(name: str) -> str:
    """Validate a project name and return its directory name.

    Hyphens become underscores, as they always have. The rejections matter more
    than the mangling: this is the only thing standing between a name typed into
    a text field and ``shutil.rmtree``.
    """
    candidate = (name or "").strip()
    if not candidate:
        raise ValueError("Project name is required.")
    if candidate in {".", ".."} or candidate.startswith("."):
        raise ValueError(f"Invalid project name {name!r}: names may not start with '.'.")
    if not _SAFE_NAME.fullmatch(candidate):
        raise ValueError(
            f"Invalid project name {name!r}. Use letters, digits, '-', '_' or '.'."
        )
    return candidate.replace("-", "_")


def project_dir_for_name(name: str) -> Path:
    """The folder for a project, whether or not it exists yet."""

    return projects_dir() / dir_name_for(name)


def index_path_for_name(name: str) -> Path:
    return project_dir_for_name(name) / INDEX_FILENAME


def step_path(directory: Path, slug: str) -> Path:
    return directory / f"{slug}.yaml"


def assert_inside_projects_dir(candidate: Path) -> Path:
    """Return ``candidate`` resolved, or raise if it is not a project folder.

    The second of two independent guards on the destructive operations (the
    first being :func:`dir_name_for`). A project folder is always exactly one
    level below the projects root, so anything else — the root itself, a
    grandchild, a path elsewhere on disk — is rejected.
    """
    root = projects_dir().resolve()
    # Checked before resolve(): resolve() follows a symlink to its target, so a
    # link sitting beside its target would otherwise pass the parent check and
    # take the rmtree with it.
    if candidate.is_symlink():
        raise ValueError(f"Refusing to operate on symlinked project path {candidate}.")
    target = candidate.resolve()
    if target == root:
        raise ValueError(f"Refusing to operate on the projects root {root}.")
    if target.parent != root:
        raise ValueError(f"{target} is not a project folder inside {root}.")
    return target


def _ensure_projects_dir() -> Path:
    root = projects_dir()
    root.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        # Matches the permissions settings.yaml's directory gets: not secret, but
        # there is no reason for a user's dataset paths to be world-readable.
        try:
            root.chmod(0o700)
        except OSError:
            pass
    return root


# ── reading ───────────────────────────────────────────────────────────────────

def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Could not parse {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(
            f"{path} must contain a mapping, not {type(data).__name__}."
        )
    return data


def read_project_folder(directory: Path) -> tuple[dict[str, Any], list[str]]:
    """Assemble a project folder into one flat dict, plus any advisory notes.

    ``index.yaml`` drives the read: a step file that is not listed is ignored
    (that is how a parked step keeps its settings), and any other file in the
    folder is simply not looked at.
    """
    index_file = directory / INDEX_FILENAME
    if not index_file.exists():
        raise ValueError(f"{directory} is not a project: no {INDEX_FILENAME}.")

    index = _load_yaml_mapping(index_file)
    notes: list[str] = []

    data: dict[str, Any] = {}
    if "name" in index:
        data["name"] = index["name"]
    for key in ("input_dir", "output_dir"):
        if key in index:
            data[key] = index[key]

    pipeline: list[dict[str, Any]] = []
    for entry in index.get("pipeline") or []:
        slug, enabled = _read_index_entry(entry, index_file)
        step_type = step_type_for_slug(slug)
        if step_type is None:
            raise ValueError(
                f"Unknown step '{slug}' in {index_file.name}. "
                f"Known: {', '.join(step_slugs())}"
            )

        step_file = step_path(directory, slug)
        if step_file.exists():
            step: dict[str, Any] = dict(_load_yaml_mapping(step_file))
        else:
            step = {}
            # Not fatal: a listed step with no file is the folder-shaped spelling
            # of a step block with no keys, which has always meant "defaults".
            # Still worth saying out loud, because a typo'd filename looks the same.
            notes.append(
                f"{index_file.name} lists '{slug}' but {slug}.yaml is missing "
                f"— using built-in defaults."
            )
        step["type"] = step_type
        if not enabled:
            step["enabled"] = False
        pipeline.append(step)

    data["pipeline"] = pipeline
    return data, notes


def read_index(directory: Path) -> dict[str, Any]:
    """Just the project's identity and step list — without opening any step file.

    Cheaper than a full read, and more robust: the library grid needs only these
    fields, so one unparseable ``<step>.yaml`` should not turn a project card
    into an error.
    """
    index_file = directory / INDEX_FILENAME
    if not index_file.exists():
        raise ValueError(f"{directory} is not a project: no {INDEX_FILENAME}.")
    return _load_yaml_mapping(index_file)


def write_index(directory: Path, data: dict[str, Any]) -> Path:
    """Rewrite a project's ``index.yaml``, leaving every ``<step>.yaml`` alone."""

    return write_yaml_atomic(
        directory / INDEX_FILENAME,
        data,
        secure_parent=True,
        header=_index_banner(),
        dumper=ProjectDumper,
    )


def rename_project_dir(source: Path, destination: Path) -> None:
    """Move a project folder, keeping every step file byte-identical."""

    assert_inside_projects_dir(source)
    _rename_dir(source, destination)


def _read_index_entry(entry: Any, index_file: Path) -> tuple[str, bool]:
    if isinstance(entry, str):
        return entry, True
    if isinstance(entry, dict):
        slug = entry.get("step")
        if not isinstance(slug, str) or not slug:
            raise ValueError(f"{index_file.name}: pipeline entries need a 'step' name.")
        return slug, bool(entry.get("enabled", True))
    raise ValueError(
        f"{index_file.name}: pipeline entries must be mappings like "
        f"{{step: caption_bbox, enabled: true}}."
    )


def list_project_names() -> list[str]:
    """Every project name in the library, read from each ``index.yaml``.

    The name comes from the file rather than the directory because the directory
    name is lossy (hyphens are stored as underscores); guessing the inverse made
    ``foo-bar`` and ``foo_bar`` indistinguishable.
    """
    root = projects_dir()
    if not root.exists():
        return []

    names: list[str] = []
    for directory in root.iterdir():
        # Dot-prefixed folders are in-flight writes (.<name>.plk_tmp), which do
        # contain a valid index.
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        index_file = directory / INDEX_FILENAME
        if not index_file.exists():
            continue
        try:
            name = _load_yaml_mapping(index_file).get("name")
        except ValueError:
            name = None
        names.append(str(name) if name else directory.name)
    return sorted(names)


# ── writing ───────────────────────────────────────────────────────────────────

def write_project_folder(directory: Path, data: dict[str, Any]) -> Path:
    """Write a whole project folder, atomically. Never mutates ``data``.

    Splitting one document into eleven files means eleven chances to be
    interrupted, and a half-written folder would *load successfully* with silent
    defaults for the missing steps — a wrong config, which is worse than a
    crash. So the folder is built under a sibling temp name and swapped in once
    it is complete.
    """
    index_data, step_bodies = _split(data)

    _ensure_projects_dir()
    parent = directory.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = parent / f".{directory.name}{_TMP_SUFFIX}"
    previous = parent / f".{directory.name}{_OLD_SUFFIX}"
    _remove_dir(staging)
    _remove_dir(previous)
    staging.mkdir(parents=True)

    try:
        write_yaml_atomic(
            staging / INDEX_FILENAME,
            index_data,
            secure_parent=True,
            header=_index_banner(),
            dumper=ProjectDumper,
        )
        for slug, body in step_bodies:
            write_yaml_atomic(
                step_path(staging, slug),
                body,
                secure_parent=True,
                header=_step_banner(slug),
                dumper=ProjectDumper,
            )
    except Exception:
        _remove_dir(staging)
        raise

    swapped = directory.exists()
    if swapped:
        _rename_dir(directory, previous)
    _rename_dir(staging, directory)
    if swapped:
        _remove_dir(previous)
    return directory


def _split(data: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[str, dict]]]:
    """Turn one flat project dict into the index plus one body per step."""

    index: dict[str, Any] = {"name": data.get("name")}
    for key in ("input_dir", "output_dir"):
        if data.get(key) is not None:
            index[key] = data[key]

    entries: list[Any] = []
    bodies: list[tuple[str, dict[str, Any]]] = []
    for raw in data.get("pipeline") or []:
        step = dict(raw)
        step_type = step.pop("type", None)
        enabled = bool(step.pop("enabled", True))
        slug = step_slug(str(step_type))
        if slug is None:
            raise ValueError(f"Unknown step type '{step_type}'.")
        entries.append(inline({"step": slug, "enabled": enabled}))
        bodies.append((slug, _styled_step_body(step)))

    index["pipeline"] = entries
    return index, bodies


def _styled_step_body(step: dict[str, Any]) -> dict[str, Any]:
    """Reorder a step body for reading and mark its short records inline."""

    body: dict[str, Any] = {}
    # substeps first: what the step *does*, before how it is tuned.
    if "substeps" in step:
        body["substeps"] = [inline(entry) for entry in step["substeps"]]
    for key, value in step.items():
        if key == "substeps":
            continue
        if key == "scorers" and isinstance(value, list):
            body[key] = [inline(entry) for entry in value]
        elif key == "resolution_buckets" and isinstance(value, list):
            body[key] = [inline(entry) for entry in value]
        else:
            body[key] = value
    return body


def _remove_dir(directory: Path) -> None:
    if not directory.exists():
        return
    try:
        shutil.rmtree(directory)
    except OSError as exc:
        raise ValueError(
            f"Could not remove {directory}: {exc}. Another program may be holding "
            f"a file open (antivirus, file sync, or an open editor)."
        ) from exc


def _rename_dir(source: Path, destination: Path) -> None:
    try:
        source.rename(destination)
    except OSError as exc:
        raise ValueError(
            f"Could not move {source} to {destination}: {exc}. Another program may "
            f"be holding a file open (antivirus, file sync, or an open editor)."
        ) from exc


# ── banners ───────────────────────────────────────────────────────────────────
#
# PyYAML cannot emit comments, so a regenerated banner is the only durable
# comment a written file can carry. The asymmetry is worth stating in the files
# themselves: index.yaml is rewritten by renames and folder-first opens, while a
# step file is written once at creation and only ever read afterwards — so notes
# a user adds to a step file survive, and notes in index.yaml do not.

def _index_banner() -> str:
    slugs = step_slugs()
    half = (len(slugs) + 1) // 2
    order = f"{', '.join(slugs[:half])},\n#     {', '.join(slugs[half:])}"
    return (
        "# PrepareLoraKit project index — the pipeline's table of contents.\n"
        "#\n"
        "# `pipeline:` owns which steps run and in what order. Each entry names a\n"
        "# sibling <step>.yaml holding that step's settings.\n"
        "#   enabled: false parks a step: it is skipped, but its file is kept.\n"
        "#   A <step>.yaml not listed here is ignored. A step listed here with no\n"
        "#   file runs on built-in defaults.\n"
        f"#   Order must follow the canonical pipeline order:\n"
        f"#     {order}\n"
        "#\n"
        "# The app rewrites this file (renames, folder-first opens), so comments\n"
        "# added HERE are not preserved. Comments in the <step>.yaml files are safe.\n"
    )


def _step_banner(slug: str) -> str:
    step_type = step_type_for_slug(slug) or slug
    substeps = ", ".join(substep_ids_for(step_type))
    lines = [
        f"# {step_type} settings. Enabled or disabled in {INDEX_FILENAME}.",
    ]
    if substeps:
        lines.append("# substeps: ordered units inside this step.")
        lines.append(f"#   {substeps}")
    lines.append("# Written once at project creation; the app does not rewrite this file.")
    return "\n".join(lines) + "\n"


__all__ = [
    "INDEX_FILENAME",
    "assert_inside_projects_dir",
    "dir_name_for",
    "index_path_for_name",
    "list_project_names",
    "project_dir_for_name",
    "projects_dir",
    "read_index",
    "read_project_folder",
    "rename_project_dir",
    "step_path",
    "write_index",
    "write_project_folder",
]
