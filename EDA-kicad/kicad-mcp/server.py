#!/usr/bin/env python3
"""
KiCad PCB MCP Server — component placement and board inspection tools.
"""

import asyncio
import json
import re
import uuid
from pathlib import Path
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

PCB_PATH = Path("/home/avery/SPIRIT/EDA-kicad/cm5-carrier.kicad_pcb")

app = Server("kicad-pcb")


# ── helpers ──────────────────────────────────────────────────────────────────

def _read_pcb() -> str:
    return PCB_PATH.read_text()


def _write_pcb(content: str) -> None:
    PCB_PATH.write_text(content)


def _board_bounds(content: str) -> dict:
    """Return xmin/xmax/ymin/ymax of Edge.Cuts outline."""
    lines = content.split("\n")
    coords = []
    for i, line in enumerate(lines):
        if "Edge.Cuts" in line:
            for j in range(max(0, i - 6), i):
                m = re.search(r"(?:start|end|center|mid)\s+([\d.\-]+)\s+([\d.\-]+)", lines[j])
                if m:
                    coords.append((float(m.group(1)), float(m.group(2))))
    if not coords:
        return {}
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return {"xmin": min(xs), "xmax": max(xs), "ymin": min(ys), "ymax": max(ys)}


def _parse_footprints(content: str) -> list[dict]:
    """Parse all footprints into dicts with ref, lib, x, y, rotation, layer."""
    results = []
    # Split on top-level footprint entries
    blocks = re.split(r"\n\t(?=\(footprint\s)", content)
    for block in blocks:
        fp_m = re.match(r"\(footprint\s+\"([^\"]+)\"", block)
        if not fp_m:
            continue
        at_m = re.search(r"\(at\s+([\d.\-]+)\s+([\d.\-]+)(?:\s+([\d.\-]+))?\)", block)
        ref_m = re.search(r"\"Reference\"\s+\"([^\"]+)\"", block)
        layer_m = re.search(r"\(layer\s+\"([^\"]+)\"", block)
        if not (at_m and ref_m):
            continue
        results.append({
            "ref": ref_m.group(1),
            "lib": fp_m.group(1),
            "x": float(at_m.group(1)),
            "y": float(at_m.group(2)),
            "rotation": float(at_m.group(3)) if at_m.group(3) else 0.0,
            "layer": layer_m.group(1) if layer_m else "F.Cu",
        })
    return results


def _move_footprint_in_content(content: str, ref: str, new_x: float, new_y: float,
                                new_rot: float | None = None) -> tuple[str, bool]:
    """
    Find footprint by reference and update its (at ...) line.
    Returns (new_content, success).
    """
    blocks = re.split(r"(\n\t(?=\(footprint\s))", content)
    out = []
    found = False
    i = 0
    while i < len(blocks):
        block = blocks[i]
        # The split inserts the delimiter as a separate element
        ref_m = re.search(r"\"Reference\"\s+\"([^\"]+)\"", block)
        if ref_m and ref_m.group(1) == ref:
            at_m = re.search(r"(\(at\s+[\d.\-]+\s+[\d.\-]+(?:\s+[\d.\-]+)?\))", block)
            if at_m:
                old_at = at_m.group(1)
                if new_rot is not None:
                    new_at = f"(at {new_x} {new_y} {new_rot})"
                else:
                    # Preserve existing rotation
                    rot_m = re.search(r"\(at\s+[\d.\-]+\s+[\d.\-]+\s+([\d.\-]+)\)", old_at)
                    if rot_m:
                        new_at = f"(at {new_x} {new_y} {rot_m.group(1)})"
                    else:
                        new_at = f"(at {new_x} {new_y})"
                block = block.replace(old_at, new_at, 1)
                found = True
        out.append(block)
        i += 1
    return "".join(out), found


# ── tool handlers ─────────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_board_info",
            description="Get PCB board outline dimensions and component count",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="list_footprints",
            description="List all footprints with reference, position, rotation, layer. "
                        "Set outside_only=true to show only components outside the board outline.",
            inputSchema={
                "type": "object",
                "properties": {
                    "outside_only": {
                        "type": "boolean",
                        "description": "Only return footprints outside the board outline",
                        "default": False,
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="move_footprint",
            description="Move a single footprint to a new (x, y) position. "
                        "Optionally set rotation in degrees.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ref": {"type": "string", "description": "Component reference, e.g. R5"},
                    "x": {"type": "number", "description": "New X position in mm"},
                    "y": {"type": "number", "description": "New Y position in mm"},
                    "rotation": {
                        "type": "number",
                        "description": "Rotation in degrees (optional, preserves existing if omitted)",
                    },
                },
                "required": ["ref", "x", "y"],
            },
        ),
        types.Tool(
            name="batch_move",
            description="Move multiple footprints at once. "
                        "Each item: {ref, x, y, rotation (optional)}.",
            inputSchema={
                "type": "object",
                "properties": {
                    "moves": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ref": {"type": "string"},
                                "x": {"type": "number"},
                                "y": {"type": "number"},
                                "rotation": {"type": "number"},
                            },
                            "required": ["ref", "x", "y"],
                        },
                    }
                },
                "required": ["moves"],
            },
        ),
        types.Tool(
            name="get_footprint",
            description="Get full details for one footprint by reference",
            inputSchema={
                "type": "object",
                "properties": {
                    "ref": {"type": "string", "description": "Component reference"}
                },
                "required": ["ref"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    content = _read_pcb()
    bounds = _board_bounds(content)
    margin = 2.0

    if name == "get_board_info":
        fps = _parse_footprints(content)
        if bounds:
            w = bounds["xmax"] - bounds["xmin"]
            h = bounds["ymax"] - bounds["ymin"]
            outside = [
                f for f in fps
                if f["x"] < bounds["xmin"] - margin
                or f["x"] > bounds["xmax"] + margin
                or f["y"] < bounds["ymin"] - margin
                or f["y"] > bounds["ymax"] + margin
            ]
            result = {
                "board_outline_mm": f"{w:.1f} x {h:.1f}",
                "bounds": bounds,
                "total_footprints": len(fps),
                "outside_board": len(outside),
            }
        else:
            result = {"total_footprints": len(fps), "error": "No Edge.Cuts found"}
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "list_footprints":
        fps = _parse_footprints(content)
        outside_only = arguments.get("outside_only", False)
        if outside_only and bounds:
            fps = [
                f for f in fps
                if f["x"] < bounds["xmin"] - margin
                or f["x"] > bounds["xmax"] + margin
                or f["y"] < bounds["ymin"] - margin
                or f["y"] > bounds["ymax"] + margin
            ]
        return [types.TextContent(type="text", text=json.dumps(fps, indent=2))]

    elif name == "move_footprint":
        ref = arguments["ref"]
        x, y = float(arguments["x"]), float(arguments["y"])
        rot = arguments.get("rotation")
        new_content, ok = _move_footprint_in_content(content, ref, x, y, rot)
        if ok:
            _write_pcb(new_content)
            return [types.TextContent(type="text", text=f"Moved {ref} to ({x}, {y})")]
        else:
            return [types.TextContent(type="text", text=f"ERROR: footprint '{ref}' not found")]

    elif name == "batch_move":
        moves = arguments["moves"]
        cur = content
        results = []
        for m in moves:
            ref = m["ref"]
            x, y = float(m["x"]), float(m["y"])
            rot = m.get("rotation")
            cur, ok = _move_footprint_in_content(cur, ref, x, y, rot)
            results.append(f"{'OK' if ok else 'NOT FOUND'}: {ref} → ({x}, {y})")
        _write_pcb(cur)
        return [types.TextContent(type="text", text="\n".join(results))]

    elif name == "get_footprint":
        ref = arguments["ref"]
        fps = _parse_footprints(content)
        match = [f for f in fps if f["ref"] == ref]
        if match:
            return [types.TextContent(type="text", text=json.dumps(match[0], indent=2))]
        else:
            return [types.TextContent(type="text", text=f"ERROR: '{ref}' not found")]

    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# ── entry point ───────────────────────────────────────────────────────────────

async def main():
    async with mcp.server.stdio.stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
