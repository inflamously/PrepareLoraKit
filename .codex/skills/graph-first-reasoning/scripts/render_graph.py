#!/usr/bin/env python3
"""Render graph-first reasoning output to Markdown, Mermaid, and PNG files."""
from __future__ import annotations

import argparse
import binascii
import math
import re
import struct
import sys
import textwrap
import zlib
from dataclasses import dataclass
from pathlib import Path


SECTION_NAMES = ("NODES", "EDGES", "KEY PATH", "ACTION", "ANSWER")


@dataclass(frozen=True)
class Node:
    tag: str
    description: str


@dataclass(frozen=True)
class Edge:
    source: str
    relation: str
    target: str


@dataclass(frozen=True)
class Graph:
    nodes: list[Node]
    edges: list[Edge]
    key_path: list[str]
    action: str
    answer: str
    raw: str


def main() -> int:
    args = parse_args()
    raw = read_input(args.input)
    graph = parse_graph(raw)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"graph_{slug(args.name)}"

    mermaid = build_mermaid(graph, title=args.title)
    md = build_markdown(graph, mermaid, title=args.title)

    md_path = output_dir / f"{stem}.md"
    mmd_path = output_dir / f"{stem}.mmd"
    png_path = output_dir / f"{stem}.png"

    md_path.write_text(md, encoding="utf-8")
    mmd_path.write_text(mermaid + "\n", encoding="utf-8")
    if not args.no_png:
        render_png(graph, png_path, title=args.title)

    print(f"Wrote {md_path}")
    print(f"Wrote {mmd_path}")
    if not args.no_png:
        print(f"Wrote {png_path}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build docs/graph artifacts from graph-first reasoning sections."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="File containing NODES/EDGES/KEY PATH/ACTION/ANSWER sections. Reads stdin when omitted.",
    )
    parser.add_argument("--name", default="reasoning", help="Output name used in graph_<name>.* files.")
    parser.add_argument("--title", default="Reasoning Graph", help="Human-readable graph title.")
    parser.add_argument("--output-dir", type=Path, default=Path("docs/graph"))
    parser.add_argument("--no-png", action="store_true", help="Write only Markdown and Mermaid artifacts.")
    return parser.parse_args()


def read_input(path: Path | None) -> str:
    if path is None:
        return sys.stdin.read()
    return path.read_text(encoding="utf-8")


def parse_graph(raw: str) -> Graph:
    sections = split_sections(raw)
    nodes = parse_nodes(sections.get("NODES", ""))
    edges = parse_edges(sections.get("EDGES", ""))
    key_path = parse_key_path(sections.get("KEY PATH", ""))
    action = parse_first_bullet(sections.get("ACTION", ""))
    answer = parse_first_bullet(sections.get("ANSWER", ""))
    validate_graph(nodes, edges, key_path)
    return Graph(nodes=nodes, edges=edges, key_path=key_path, action=action, answer=answer, raw=raw)


def split_sections(raw: str) -> dict[str, str]:
    section_re = re.compile(r"^(NODES|EDGES|KEY PATH|ACTION|ANSWER):\s*$", re.MULTILINE)
    matches = list(section_re.finditer(raw))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        sections[match.group(1)] = raw[start:end].strip()
    return sections


def parse_nodes(text: str) -> list[Node]:
    nodes: list[Node] = []
    for line in bullet_lines(text):
        if "=" not in line:
            raise ValueError(f"Node line must use 'tag = description': {line}")
        tag, description = line.split("=", 1)
        nodes.append(Node(tag=tag.strip(), description=description.strip()))
    return nodes


def parse_edges(text: str) -> list[Edge]:
    edges: list[Edge] = []
    edge_re = re.compile(r"^(.+?)\s+--(.+?)-->\s+(.+?)$")
    for line in bullet_lines(text):
        match = edge_re.match(line)
        if not match:
            raise ValueError(f"Edge line must use 'source --relation--> target': {line}")
        edges.append(
            Edge(
                source=match.group(1).strip(),
                relation=match.group(2).strip(),
                target=match.group(3).strip(),
            )
        )
    return edges


def parse_key_path(text: str) -> list[str]:
    for line in bullet_lines(text):
        return [part.strip() for part in line.split("->") if part.strip()]
    return []


def parse_first_bullet(text: str) -> str:
    for line in bullet_lines(text):
        return line.strip()
    return ""


def bullet_lines(text: str) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("* "):
            lines.append(line[2:].strip())
    return lines


def validate_graph(nodes: list[Node], edges: list[Edge], key_path: list[str]) -> None:
    if not nodes:
        raise ValueError("No nodes found.")
    known = {node.tag for node in nodes}
    missing = []
    for edge in edges:
        if edge.source not in known:
            missing.append(edge.source)
        if edge.target not in known:
            missing.append(edge.target)
    for tag in key_path:
        if tag not in known:
            missing.append(tag)
    if missing:
        names = ", ".join(sorted(set(missing)))
        raise ValueError(f"Unknown node tag(s): {names}")


def build_mermaid(graph: Graph, *, title: str) -> str:
    id_by_tag = {node.tag: f"n_{index}_{slug(node.tag)}" for index, node in enumerate(graph.nodes)}
    key_edges = {
        (left, right)
        for left, right in zip(graph.key_path, graph.key_path[1:])
    }
    lines = [
        "---",
        f"title: {title.replace(chr(34), chr(39))}",
        "---",
        "flowchart LR",
        "  classDef node fill:#f8fafc,stroke:#334155,stroke-width:1px,color:#0f172a;",
        "  classDef key fill:#fff7ed,stroke:#ea580c,stroke-width:2px,color:#7c2d12;",
    ]
    for node in graph.nodes:
        label = mermaid_label(f"{node.tag}: {node.description}")
        lines.append(f'  {id_by_tag[node.tag]}["{label}"]')
        lines.append(f"  class {id_by_tag[node.tag]} {'key' if node.tag in graph.key_path else 'node'};")
    for index, edge in enumerate(graph.edges):
        edge_line = (
            f'  {id_by_tag[edge.source]} -- "{mermaid_label(edge.relation)}" --> '
            f"{id_by_tag[edge.target]}"
        )
        lines.append(edge_line)
        if (edge.source, edge.target) in key_edges:
            lines.append(f"  linkStyle {index} stroke:#ea580c,stroke-width:3px;")
    return "\n".join(lines)


def build_markdown(graph: Graph, mermaid: str, *, title: str) -> str:
    return "\n".join(
        [
            f"# {title}",
            "",
            "```mermaid",
            mermaid,
            "```",
            "",
            graph.raw.strip(),
            "",
        ]
    )


def render_png(graph: Graph, output_path: Path, *, title: str) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        render_basic_png(graph, output_path)
        return

    font = ImageFont.load_default()
    margin = 28
    box_w = 230
    box_h = 74
    gap_x = 44
    gap_y = 28
    title_h = 46
    columns = min(4, max(1, math.ceil(math.sqrt(len(graph.nodes)))))
    rows = math.ceil(len(graph.nodes) / columns)
    width = margin * 2 + columns * box_w + (columns - 1) * gap_x
    height = margin * 2 + title_h + rows * box_h + (rows - 1) * gap_y

    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    draw.text((margin, margin), title, fill="#0f172a", font=font)

    positions: dict[str, tuple[int, int, int, int]] = {}
    for index, node in enumerate(graph.nodes):
        col = index % columns
        row = index // columns
        x0 = margin + col * (box_w + gap_x)
        y0 = margin + title_h + row * (box_h + gap_y)
        positions[node.tag] = (x0, y0, x0 + box_w, y0 + box_h)

    for edge in graph.edges:
        draw_edge(draw, positions[edge.source], positions[edge.target])

    key_nodes = set(graph.key_path)
    for node in graph.nodes:
        box = positions[node.tag]
        fill = "#fff7ed" if node.tag in key_nodes else "#f8fafc"
        outline = "#ea580c" if node.tag in key_nodes else "#334155"
        draw.rounded_rectangle(box, radius=8, fill=fill, outline=outline, width=2)
        draw_wrapped(draw, box, f"{node.tag}: {node.description}", font)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def render_basic_png(graph: Graph, output_path: Path) -> None:
    """Small dependency-free PNG fallback.

    The Markdown/Mermaid files carry the readable labels. This fallback keeps a
    visual map available even when Pillow is not installed.
    """

    margin = 28
    box_w = 170
    box_h = 54
    gap_x = 42
    gap_y = 30
    title_h = 24
    columns = min(4, max(1, math.ceil(math.sqrt(len(graph.nodes)))))
    rows = math.ceil(len(graph.nodes) / columns)
    width = margin * 2 + columns * box_w + (columns - 1) * gap_x
    height = margin * 2 + title_h + rows * box_h + (rows - 1) * gap_y
    canvas = bytearray([255, 255, 255] * width * height)

    positions: dict[str, tuple[int, int, int, int]] = {}
    for index, node in enumerate(graph.nodes):
        col = index % columns
        row = index // columns
        x0 = margin + col * (box_w + gap_x)
        y0 = margin + title_h + row * (box_h + gap_y)
        positions[node.tag] = (x0, y0, x0 + box_w, y0 + box_h)

    for edge in graph.edges:
        draw_basic_edge(canvas, width, positions[edge.source], positions[edge.target])

    key_nodes = set(graph.key_path)
    for node in graph.nodes:
        x0, y0, x1, y1 = positions[node.tag]
        fill = (255, 247, 237) if node.tag in key_nodes else (248, 250, 252)
        outline = (234, 88, 12) if node.tag in key_nodes else (51, 65, 85)
        fill_rect(canvas, width, x0, y0, x1, y1, fill)
        stroke_rect(canvas, width, x0, y0, x1, y1, outline)
        # tag bars give node-count/shape cues in the fallback without bundling a font.
        bar_w = min(box_w - 20, 18 + len(node.tag) * 5)
        fill_rect(canvas, width, x0 + 10, y0 + 12, x0 + 10 + bar_w, y0 + 18, outline)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_png(output_path, width, height, canvas)


def draw_basic_edge(
    canvas: bytearray,
    width: int,
    source_box: tuple[int, int, int, int],
    target_box: tuple[int, int, int, int],
) -> None:
    sx = source_box[2]
    sy = (source_box[1] + source_box[3]) // 2
    tx = target_box[0]
    ty = (target_box[1] + target_box[3]) // 2
    if tx < sx:
        sx = (source_box[0] + source_box[2]) // 2
        sy = source_box[3]
        tx = (target_box[0] + target_box[2]) // 2
        ty = target_box[1]
    draw_line(canvas, width, sx, sy, tx, ty, (148, 163, 184))
    fill_rect(canvas, width, tx - 5, ty - 5, tx + 1, ty + 6, (148, 163, 184))


def set_pixel(canvas: bytearray, width: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    if x < 0 or y < 0:
        return
    index = (y * width + x) * 3
    if index + 2 >= len(canvas):
        return
    canvas[index:index + 3] = bytes(color)


def fill_rect(
    canvas: bytearray,
    width: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
) -> None:
    for y in range(max(0, y0), max(0, y1)):
        for x in range(max(0, x0), max(0, x1)):
            set_pixel(canvas, width, x, y, color)


def stroke_rect(
    canvas: bytearray,
    width: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
) -> None:
    draw_line(canvas, width, x0, y0, x1, y0, color)
    draw_line(canvas, width, x1, y0, x1, y1, color)
    draw_line(canvas, width, x1, y1, x0, y1, color)
    draw_line(canvas, width, x0, y1, x0, y0, color)


def draw_line(
    canvas: bytearray,
    width: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
) -> None:
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        set_pixel(canvas, width, x0, y0, color)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def write_png(path: Path, width: int, height: int, rgb: bytearray) -> None:
    rows = []
    row_len = width * 3
    for y in range(height):
        rows.append(b"\x00" + bytes(rgb[y * row_len:(y + 1) * row_len]))
    raw = b"".join(rows)
    with path.open("wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        write_png_chunk(fh, b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        write_png_chunk(fh, b"IDAT", zlib.compress(raw, level=9))
        write_png_chunk(fh, b"IEND", b"")


def write_png_chunk(fh, chunk_type: bytes, data: bytes) -> None:
    fh.write(struct.pack(">I", len(data)))
    fh.write(chunk_type)
    fh.write(data)
    crc = binascii.crc32(chunk_type)
    crc = binascii.crc32(data, crc)
    fh.write(struct.pack(">I", crc & 0xFFFFFFFF))


def draw_edge(draw, source_box: tuple[int, int, int, int], target_box: tuple[int, int, int, int]) -> None:
    sx = source_box[2]
    sy = (source_box[1] + source_box[3]) // 2
    tx = target_box[0]
    ty = (target_box[1] + target_box[3]) // 2
    if tx < sx:
        sx = (source_box[0] + source_box[2]) // 2
        sy = source_box[3]
        tx = (target_box[0] + target_box[2]) // 2
        ty = target_box[1]
    draw.line((sx, sy, tx, ty), fill="#94a3b8", width=2)
    draw.polygon(((tx, ty), (tx - 7, ty - 4), (tx - 7, ty + 4)), fill="#94a3b8")


def draw_wrapped(draw, box: tuple[int, int, int, int], text: str, font) -> None:
    x0, y0, x1, _y1 = box
    lines = textwrap.wrap(text, width=max(20, int((x1 - x0 - 18) / 6)), max_lines=4, placeholder="...")
    y = y0 + 8
    for line in lines:
        draw.text((x0 + 9, y), line, fill="#0f172a", font=font)
        y += 14


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_")
    return cleaned or "graph"


def mermaid_label(value: str) -> str:
    return value.replace('"', "'").replace("\n", "<br/>")


if __name__ == "__main__":
    raise SystemExit(main())
