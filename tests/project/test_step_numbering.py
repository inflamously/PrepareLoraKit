"""Keep step numbering from rotting back in.

A "Step 3" in a docstring or a window title is a denormalized copy of
``StepDefinition.order`` with nothing keeping it in sync. Five of them were
already wrong when this test was written — ``vae_gate`` said "Step 4" while it
ran sixth, ``audit`` said "Step 6" while it ran seventh — so the convention is
now to name the step instead of numbering it.

The README stage table is the one place a number is genuinely useful to a
reader, so it is checked against the code rather than removed.
"""
import re

from prepare_lora_kit.paths import PROJECT_ROOT
from prepare_lora_kit.pipeline import step_slug, step_types

SOURCE_ROOTS = ("prepare_lora_kit", "prepare_lora_kit_ui")
STEP_NUMBER = re.compile(r"\bStep\s+\d")
README = PROJECT_ROOT / "README.md"


def test_no_source_file_hardcodes_a_step_number():
    """Name the step; the number lives in ``STEP_DEFINITIONS.order`` alone."""
    offenders = []
    for root in SOURCE_ROOTS:
        for path in sorted((PROJECT_ROOT / root).rglob("*.py")):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if STEP_NUMBER.search(line):
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{lineno}: {line.strip()}")

    assert not offenders, "hardcoded step numbers go stale — name the step:\n" + "\n".join(
        offenders
    )


def _readme_stage_rows() -> list[list[str]]:
    """The `## Pipeline Stages` table body, as a list of stripped cell lists."""
    section = README.read_text(encoding="utf-8").split("## Pipeline Stages", 1)[1]
    rows = []
    for line in section.splitlines():
        if not line.startswith("|"):
            if rows:  # table ended
                break
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] in ("Step", "---"):
            continue
        rows.append(cells)
    return rows


def test_readme_stage_table_matches_the_canonical_order():
    rows = _readme_stage_rows()
    expected = step_types()

    assert [row[0] for row in rows] == [str(i) for i in range(len(expected))]
    assert [row[1] for row in rows] == [f"`{step_type}`" for step_type in expected]
    assert [row[2] for row in rows] == [f"`{step_slug(step_type)}.yaml`" for step_type in expected]
