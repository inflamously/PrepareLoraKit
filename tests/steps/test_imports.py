"""Import smoke tests for step packages and modules."""
from __future__ import annotations

import importlib
import pkgutil

import prepare_lora_kit.steps as steps_pkg


def _step_module_names() -> list[str]:
    names = [steps_pkg.__name__]
    names.extend(
        module_info.name
        for module_info in pkgutil.walk_packages(
            steps_pkg.__path__,
            prefix=f"{steps_pkg.__name__}.",
        )
    )
    return sorted(names)


def test_all_step_modules_import():
    for module_name in _step_module_names():
        importlib.import_module(module_name)


def test_step_packages_export_callable_run():
    for module_info in pkgutil.iter_modules(steps_pkg.__path__):
        if not module_info.ispkg:
            continue

        package_name = f"{steps_pkg.__name__}.{module_info.name}"
        try:
            importlib.import_module(f"{package_name}.step")
        except ModuleNotFoundError as exc:
            if exc.name == f"{package_name}.step":
                continue
            raise

        package = importlib.import_module(package_name)
        assert callable(getattr(package, "run", None)), f"{package_name} must export run"
