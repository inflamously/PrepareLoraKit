"""Create, find, rename, copy and delete projects on disk.

Every project is a folder under ``~/.prepare_lora_kit/projects/`` — see
:mod:`prepare_lora_kit.project.store` for its shape. This module is the only
place that mutates the library, and it works exclusively from project *names*:
each one goes through ``store.dir_name_for`` before it becomes a path, which is
the first of the two guards standing between a name typed into the UI and
``shutil.rmtree``.

Two properties are worth preserving deliberately, because both are easy to
"simplify" away:

* **Renames move the directory; they never rewrite it.** Only ``index.yaml`` is
  touched. A user's ``<step>.yaml`` files — including any comments they added —
  come through byte-for-byte.
* **``load`` raises ``ValueError`` for an unknown project.** ``cli/run.py``
  catches exactly that to offer creating the project, and ``cli/step`` turns it
  into a ``BadParameter``.
"""
from pathlib import Path
from typing import Any

import shutil

from prepare_lora_kit.project.base import ProjectConfig
from prepare_lora_kit.project.defaults import default_pipeline
from prepare_lora_kit.project import store


def config_path_for_name(name: str) -> Path:
    """The project's folder. Named for its callers; it is a directory now."""

    return store.project_dir_for_name(name)


def index_path_for_name(name: str) -> Path:
    """The project's ``index.yaml`` — the file every metadata write touches."""

    return store.index_path_for_name(name)


def default_project_data(
    name: str,
    input_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    from prepare_lora_kit.settings.seeding import apply_settings_to_pipeline

    data: dict[str, Any] = {
        "name": name,
    }
    if input_dir is not None:
        data["input_dir"] = str(input_dir)
    if output_dir is not None:
        data["output_dir"] = str(output_dir)
    # Global settings are seeded here, at write time, and never consulted again:
    # from now on this project's own files are the only thing that decides how it runs.
    data["pipeline"] = apply_settings_to_pipeline(default_pipeline())
    return data


def write_default_project(
    name: str,
    input_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> Path:
    """Write a fully-defaulted project folder and return its path."""

    directory = store.project_dir_for_name(name)
    return store.write_project_folder(
        directory, default_project_data(name, input_dir, output_dir)
    )


def create_project(
    name: str,
    input_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> Path:
    """Create a new project folder. Raises if a project with this name exists."""

    directory = store.project_dir_for_name(name)
    if directory.exists():
        raise ValueError(f"A project named '{name}' already exists.")
    return write_default_project(
        name.strip(),
        input_dir=input_dir or None,
        output_dir=output_dir or None,
    )


def update_project_meta(
    orig_name: str,
    name: str,
    input_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> Path:
    """Patch a project's identity, preserving every step file untouched.

    Supports renaming: when ``name`` differs from ``orig_name`` the folder itself
    is moved.
    """
    src_dir = store.project_dir_for_name(orig_name)
    if not src_dir.is_dir():
        raise ValueError(f"Project '{orig_name}' does not exist.")

    dst_dir = store.project_dir_for_name(name)
    # On a case-insensitive filesystem (Windows, default macOS) "demo" and "Demo"
    # are the same directory, so a case-only rename must not read as a collision
    # — nor as a move, which Path.rename may treat as a no-op or an error there.
    case_only = dst_dir != src_dir and dst_dir.exists() and dst_dir.samefile(src_dir)
    if dst_dir != src_dir and dst_dir.exists() and not case_only:
        raise ValueError(f"A project named '{name}' already exists.")

    if dst_dir != src_dir and not case_only:
        # Move first, then patch index.yaml at the new location. The other order
        # can be interrupted between the two writes and leave the *old* folder
        # claiming the *new* name — and since list_projects reads names out of
        # index.yaml, that state is reported as the new project until something
        # else creates it and shadows it. This order can only ever leave a
        # correctly-located folder whose index still says the old name, which
        # loads fine.
        store.rename_project_dir(src_dir, dst_dir)
        target_dir = dst_dir
    else:
        # Folder casing is an implementation detail: the displayed name comes
        # from index.yaml, so patching it is the whole rename.
        target_dir = src_dir

    _patch_index(
        target_dir,
        name=name.strip(),
        input_dir=input_dir or None,
        output_dir=output_dir or None,
    )
    return target_dir


def delete_project(name: str) -> None:
    """Remove a project's whole folder (idempotent)."""

    directory = store.project_dir_for_name(name)
    if not directory.exists():
        return
    store.assert_inside_projects_dir(directory)
    shutil.rmtree(directory)


def duplicate_project(name: str, new_name: str | None = None) -> str:
    """Copy a project's folder to a new name and return that name.

    When ``new_name`` is omitted, an available ``<name>_copy`` / ``<name>_copy2``
    name is chosen automatically.

    ``copytree`` rather than a load/dump round-trip, so the copy is byte-identical
    — the previous implementation reserialized the whole document and silently
    stripped any comment the user had written.
    """
    src_dir = store.project_dir_for_name(name)
    if not src_dir.is_dir():
        raise ValueError(f"Project '{name}' does not exist.")

    if new_name:
        target = new_name.strip()
        if store.project_dir_for_name(target).exists():
            raise ValueError(f"A project named '{target}' already exists.")
    else:
        target = f"{name}_copy"
        suffix = 2
        while store.project_dir_for_name(target).exists():
            target = f"{name}_copy{suffix}"
            suffix += 1

    dst_dir = store.project_dir_for_name(target)
    shutil.copytree(src_dir, dst_dir)
    _patch_index(dst_dir, name=target)
    return target


def set_project_input_dir(name: str, input_dir: Path | str) -> Path:
    """Persist input_dir on an existing project without touching its step files."""

    directory = store.project_dir_for_name(name)
    if not (directory / store.INDEX_FILENAME).exists():
        return write_default_project(name, input_dir)

    _patch_index(directory, input_dir=input_dir)
    return directory


def load_or_create_for_input(input_dir: Path | str) -> ProjectConfig:
    resolved = Path(input_dir).expanduser().resolve()
    name = resolved.name
    set_project_input_dir(name, resolved)
    return load(name)


def load(name: str) -> ProjectConfig:
    """Load a ProjectConfig by name from ~/.prepare_lora_kit/projects/<name>/."""

    directory = store.project_dir_for_name(name)
    if not (directory / store.INDEX_FILENAME).exists():
        available = ", ".join(list_projects()) or "(none)"
        raise ValueError(f"Unknown project '{name}'. Available: {available}")

    data, notes = store.read_project_folder(directory)
    if notes:
        # Lazily imported (as every other reporter caller does) to keep rich off
        # the import path of the UI bridge.
        from prepare_lora_kit.report import reporter

        for note in notes:
            reporter.warn(note)
    return ProjectConfig.from_data(data)


def list_projects() -> list[str]:
    return store.list_project_names()


def _patch_index(directory: Path, **fields: Any) -> None:
    """Rewrite only ``index.yaml``, leaving every ``<step>.yaml`` alone.

    Passing a field sets it; passing it as ``None`` removes the key, matching the
    "absent means unset" convention the rest of the config uses. A field not
    passed at all is left exactly as it was — which is why ``duplicate_project``
    can rename a copy without disturbing its dirs, and ``set_project_input_dir``
    cannot wipe an ``output_dir`` it never saw.
    """
    data = store.read_index(directory)
    for key, value in fields.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = str(value)
    if not data.get("name"):
        raise ValueError("Project name is required.")
    store.write_index(directory, data)
