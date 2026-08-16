#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, json, math, os, re, shutil
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.affinity import translate
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from shapely.ops import unary_union

LDU_MM = 0.4
OFFSET_MM = 0.1
AXIS_NAMES = {0: "YZ", 1: "XZ", 2: "XY"}

@dataclass
class PartResult:
    design_id: str
    status: str
    source_file: str | None
    projection: str | None
    width_mm: float | None
    height_mm: float | None
    thickness_mm: float | None
    area_mm2: float | None
    svg_file: str | None
    error: str | None = None


def clean_ref(name: str) -> str:
    return name.strip().replace("\\", "/").lower()


class LDraw:
    def __init__(self, root: Path):
        self.root = root
        self.cache: dict[Path, np.ndarray] = {}
        self.part_index: dict[str, list[Path]] = {}
        for path in (root / "parts").rglob("*.dat"):
            self.part_index.setdefault(path.stem.lower(), []).append(path)

    @staticmethod
    def normalise_candidate(value: str) -> str:
        value = value.strip().lower().replace("\\", "/")
        if value.endswith(".dat"):
            value = value[:-4]
        return value

    def part_path(self, design_id: str, allow_prefix: bool = True) -> tuple[Path | None, str]:
        key = self.normalise_candidate(design_id)
        exact = self.root / "parts" / f"{key}.dat"
        if exact.exists():
            return exact, "exact"
        matches = self.part_index.get(key, [])
        if matches:
            return sorted(matches, key=lambda p: (len(p.name), str(p)))[0], "indexed"
        if allow_prefix:
            # LEGO/Rebrickable IDs occasionally have an LDraw suffix. Prefer the shortest numeric-prefix match.
            prefix = [p for stem, ps in self.part_index.items() if stem.startswith(key) for p in ps]
            if prefix:
                return sorted(prefix, key=lambda p: (len(p.stem), str(p)))[0], "prefix"
        return None, "missing"

    def resolve_ref(self, current: Path, ref: str) -> Path | None:
        r = clean_ref(ref)
        candidates = [
            current.parent / r,
            self.root / r,
            self.root / "parts" / r,
            self.root / "p" / r,
            self.root / "parts" / "s" / r.removeprefix("s/"),
            self.root / "p" / "48" / r.removeprefix("48/"),
            self.root / "p" / "8" / r.removeprefix("8/"),
        ]
        for path in candidates:
            if path.exists():
                return path.resolve()
        return None

    def triangles(self, path: Path, stack: tuple[Path, ...] = ()) -> np.ndarray:
        path = path.resolve()
        if path in self.cache:
            return self.cache[path]
        if path in stack or len(stack) > 70:
            return np.empty((0, 3, 3), dtype=float)
        triangles: list[np.ndarray] = []
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            return np.empty((0, 3, 3), dtype=float)
        for line in lines:
            tokens = line.strip().split()
            if not tokens:
                continue
            kind = tokens[0]
            try:
                if kind == "1" and len(tokens) >= 15:
                    t = np.array([float(v) for v in tokens[2:5]], dtype=float)
                    m = np.array([float(v) for v in tokens[5:14]], dtype=float).reshape(3, 3)
                    child = self.resolve_ref(path, " ".join(tokens[14:]))
                    if child is None:
                        continue
                    child_tri = self.triangles(child, stack + (path,))
                    if len(child_tri):
                        transformed = child_tri @ m.T + t
                        triangles.append(transformed)
                elif kind in ("3", "4"):
                    count = 3 if kind == "3" else 4
                    vals = [float(v) for v in tokens[2:2 + count * 3]]
                    pts = np.array(vals, dtype=float).reshape(count, 3)
                    if count == 3:
                        triangles.append(pts[None, :, :])
                    else:
                        triangles.append(np.array([[pts[0], pts[1], pts[2]], [pts[0], pts[2], pts[3]]]))
            except (ValueError, IndexError):
                continue
        out = np.concatenate(triangles, axis=0) if triangles else np.empty((0, 3, 3), dtype=float)
        self.cache[path] = out
        return out


class AliasResolver:
    """Resolve modern LEGO Design IDs to Rebrickable/LDraw part numbers.

    `elements.csv` is the strongest bridge because it links an exact LEGO element
    number and design ID to a Rebrickable part_num. `part_relationships.csv` then
    expands known mold/replacement/alias relationships.
    """

    def __init__(self, elements: Path | None = None, relationships: Path | None = None):
        self.by_element: dict[str, set[str]] = defaultdict(set)
        self.by_design: dict[str, set[str]] = defaultdict(set)
        self.graph: dict[str, set[str]] = defaultdict(set)
        if elements and elements.exists():
            with elements.open(encoding="utf-8-sig", errors="ignore") as handle:
                for row in csv.DictReader(handle):
                    part = (row.get("part_num") or "").strip()
                    element = (row.get("element_id") or "").strip()
                    design = (row.get("design_id") or "").strip()
                    if not part:
                        continue
                    if element:
                        self.by_element[element].add(part)
                    if design:
                        self.by_design[design].add(part)
        if relationships and relationships.exists():
            with relationships.open(encoding="utf-8-sig", errors="ignore") as handle:
                for row in csv.DictReader(handle):
                    rel = (row.get("rel_type") or "").strip().upper()
                    child = (row.get("child_part_num") or "").strip()
                    parent = (row.get("parent_part_num") or "").strip()
                    if rel not in {"A", "M", "R", "T"} or not child or not parent:
                        continue
                    self.graph[child].add(parent)
                    self.graph[parent].add(child)

    def candidates(self, design_id: str, inventory_rows: list[dict], max_depth: int = 2):
        ordered: list[tuple[str, str]] = [(design_id, "design_id")]
        for part in sorted(self.by_design.get(design_id, set())):
            ordered.append((part, "design_alias"))
        for row in inventory_rows:
            for part in sorted(self.by_element.get(row.get("ElementID", ""), set())):
                ordered.append((part, "element_alias"))

        seen = set()
        seed_parts = []
        for value, source in ordered:
            if value and value not in seen:
                seen.add(value); seed_parts.append(value)
                yield value, source, 0

        queue = deque((part, 0) for part in seed_parts)
        while queue:
            part, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for related in sorted(self.graph.get(part, set())):
                if related in seen:
                    continue
                seen.add(related)
                queue.append((related, depth + 1))
                yield related, "relationship_alias", depth + 1


def filled(geom):
    if geom.is_empty:
        return geom
    if isinstance(geom, Polygon):
        return Polygon(geom.exterior)
    if isinstance(geom, MultiPolygon):
        return MultiPolygon([Polygon(p.exterior) for p in geom.geoms if not p.is_empty])
    if isinstance(geom, GeometryCollection):
        polys = [Polygon(p.exterior) for p in geom.geoms if isinstance(p, Polygon)]
        return unary_union(polys) if polys else geom
    return geom


def project(triangles: np.ndarray, normal_axis: int):
    keep = [axis for axis in range(3) if axis != normal_axis]
    polys = []
    for tri in triangles:
        p = tri[:, keep] * LDU_MM
        poly = Polygon(p)
        if poly.is_valid and poly.area > 0.002:
            polys.append(poly)
    if not polys:
        return None
    geom = filled(unary_union(polys).buffer(0))
    if geom.is_empty:
        return None
    geom = geom.buffer(0.03, join_style=2).buffer(-0.03, join_style=2).simplify(0.05, preserve_topology=True)
    geom = filled(geom)
    minx, miny, maxx, maxy = geom.bounds
    geom = translate(geom, xoff=-minx, yoff=-miny)
    thickness = float(np.ptp(triangles[:, :, normal_axis]) * LDU_MM)
    return geom, maxx - minx, maxy - miny, thickness


def choose_projection(triangles: np.ndarray):
    candidates = []
    for axis in (0, 1, 2):
        result = project(triangles, axis)
        if result is None:
            continue
        geom, width, height, thickness = result
        bbox_area = max(width * height, 0.001)
        fill_ratio = geom.area / bbox_area
        score = geom.area * (0.75 + 0.25 * fill_ratio) / ((max(thickness, 0.5)) ** 0.12)
        candidates.append((score, axis, geom, width, height, thickness))
    return max(candidates, key=lambda item: item[0]) if candidates else None


def polygon_path(poly: Polygon, y_max: float) -> str:
    coords = list(poly.exterior.coords)
    if not coords:
        return ""
    commands = [f"M {coords[0][0]:.3f} {y_max - coords[0][1]:.3f}"]
    commands.extend(f"L {x:.3f} {y_max - y:.3f}" for x, y in coords[1:])
    commands.append("Z")
    return " ".join(commands)


def write_svg(geom, width: float, height: float, path: Path):
    buffered = filled(geom.buffer(OFFSET_MM, join_style=2))
    minx, miny, maxx, maxy = buffered.bounds
    buffered = translate(buffered, xoff=-minx, yoff=-miny)
    width, height = maxx - minx, maxy - miny
    polys = [buffered] if isinstance(buffered, Polygon) else list(buffered.geoms)
    d = " ".join(polygon_path(poly, height) for poly in polys if isinstance(poly, Polygon))
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.3f} {height:.3f}" '
        f'width="{width:.3f}mm" height="{height:.3f}mm"><path d="{d}" fill="#111"/></svg>',
        encoding="utf-8",
    )
    return width, height


def storage_mode(row: dict, width: float, height: float, thickness: float):
    qty = int(row["Qty"])
    name = row["ElementName"].upper()
    if any(key in name for key in ("HUB MOTOR", "TACHO MOTOR", "SENSOR")):
        return "critical_nest", min(42.0, thickness + 4.0)
    stack = qty * max(thickness, 1.0) + 2.0
    if qty > 12:
        return "deep_counted_bin", 42.0
    if max(width, height) > 60 and min(width, height) < 16 and qty >= 4:
        return "edge_magazine", min(42.0, stack)
    if stack > 42:
        return "edge_magazine", 42.0
    return "shadow_stack", min(42.0, stack)


def font(size: int, bold: bool = False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def atlas(results: list[PartResult], output: Path):
    cols = 14
    cell_w, cell_h = 190, 170
    rows = math.ceil(len(results) / cols)
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(canvas)
    for index, result in enumerate(results):
        x = (index % cols) * cell_w
        y = (index // cols) * cell_h
        draw.rounded_rectangle((x + 3, y + 3, x + cell_w - 3, y + cell_h - 3), radius=10, outline="#cfd4da", width=2)
        if result.svg_file:
            # Pillow cannot render SVG. Draw a bounding-box proxy and keep the exact SVG beside the atlas.
            w, h = result.width_mm or 1, result.height_mm or 1
            scale = min((cell_w - 28) / max(w, 1), (cell_h - 55) / max(h, 1))
            rw, rh = w * scale, h * scale
            draw.rounded_rectangle((x + (cell_w-rw)/2, y + 16 + (cell_h-55-rh)/2, x + (cell_w+rw)/2, y + 16 + (cell_h-55+rh)/2), radius=4, fill="#202428")
        else:
            draw.line((x+30,y+30,x+cell_w-30,y+cell_h-55), fill="#c33", width=4)
            draw.line((x+cell_w-30,y+30,x+30,y+cell_h-55), fill="#c33", width=4)
        draw.text((x+9, y+cell_h-34), result.design_id, font=font(14, True), fill="#111")
        draw.text((x+9, y+cell_h-18), result.status, font=font(11), fill="#555")
    canvas.save(output, optimize=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ldraw", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--elements", type=Path)
    parser.add_argument("--relationships", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    svg_dir = args.output / "svg"
    svg_dir.mkdir(exist_ok=True)

    inventory = list(csv.DictReader(args.inventory.open(encoding="utf-8-sig")))
    design_ids = sorted({row["DesignID"] for row in inventory}, key=lambda value: (len(value), value))
    library = LDraw(args.ldraw)
    aliases = AliasResolver(args.elements, args.relationships)
    rows_by_design: dict[str, list[dict]] = defaultdict(list)
    for row in inventory:
        rows_by_design[row["DesignID"]].append(row)
    results: list[PartResult] = []
    geometry_by_design: dict[str, dict] = {}

    for index, design_id in enumerate(design_ids, 1):
        source = None
        mapping_status = "missing"
        selected_candidate = None
        alias_depth = None
        # First pass requires exact/indexed candidate matches to avoid unrelated numeric prefixes.
        candidate_list = list(aliases.candidates(design_id, rows_by_design[design_id]))
        for candidate, candidate_source, depth in candidate_list:
            found, found_status = library.part_path(candidate, allow_prefix=False)
            if found is not None:
                source = found
                selected_candidate = candidate
                alias_depth = depth
                mapping_status = "exact" if candidate == design_id and found_status == "exact" else candidate_source
                break
        # Second pass allows suffix/prefix variants only after exact aliases have been exhausted.
        if source is None:
            for candidate, candidate_source, depth in candidate_list:
                found, found_status = library.part_path(candidate, allow_prefix=True)
                if found is not None:
                    source = found
                    selected_candidate = candidate
                    alias_depth = depth
                    if candidate == design_id:
                        mapping_status = found_status
                    else:
                        mapping_status = candidate_source + "_" + found_status
                    break
        if source is None:
            result = PartResult(design_id, "missing", None, None, None, None, None, None, None, "No LDraw or element/relationship alias part file")
            results.append(result)
            print(f"[{index:03d}/{len(design_ids)}] {design_id} missing", flush=True)
            continue
        triangles = library.triangles(source)
        selected = choose_projection(triangles)
        if selected is None:
            result = PartResult(design_id, "no_faces", str(source.relative_to(args.ldraw)), None, None, None, None, None, None, "No projected polygon")
            results.append(result)
            print(f"[{index:03d}/{len(design_ids)}] {design_id} no_faces", flush=True)
            continue
        _, axis, geom, width, height, thickness = selected
        svg_path = svg_dir / f"{design_id}.svg"
        buffered_w, buffered_h = write_svg(geom, width, height, svg_path)
        status = "exact" if mapping_status == "exact" else mapping_status
        result = PartResult(design_id, status, str(source.relative_to(args.ldraw)), AXIS_NAMES[axis], round(buffered_w, 3), round(buffered_h, 3), round(thickness, 3), round(geom.area, 3), str(svg_path.relative_to(args.output)))
        results.append(result)
        geometry_by_design[design_id] = {
            "width_mm": buffered_w,
            "height_mm": buffered_h,
            "thickness_mm": thickness,
            "projection": AXIS_NAMES[axis],
            "source_file": str(source.relative_to(args.ldraw)),
            "status": status,
            "resolved_candidate": selected_candidate,
            "alias_depth": alias_depth,
        }
        print(f"[{index:03d}/{len(design_ids)}] {design_id} {status} {buffered_w:.1f}x{buffered_h:.1f}x{thickness:.1f}", flush=True)

    rows_out = []
    colour_area: dict[str, float] = {}
    for row in inventory:
        geom = geometry_by_design.get(row["DesignID"])
        if geom:
            width, height, thickness = geom["width_mm"], geom["height_mm"], geom["thickness_mm"]
            mode, depth = storage_mode(row, width, height, thickness)
            floor_w = max(16.0, width + 4.0)
            floor_h = max(16.0, height + 4.0)
        else:
            width = height = thickness = None
            mode, depth = "manual_review", 20.0
            floor_w = floor_h = 24.0
        floor_area = floor_w * floor_h
        colour_area[row["Colour"]] = colour_area.get(row["Colour"], 0.0) + floor_area
        rows_out.append({
            **row,
            "GeometryStatus": geom["status"] if geom else "missing",
            "Projection": geom["projection"] if geom else "",
            "WidthMM": round(width, 3) if width is not None else "",
            "HeightMM": round(height, 3) if height is not None else "",
            "ThicknessMM": round(thickness, 3) if thickness is not None else "",
            "StorageMode": mode,
            "RecommendedDepthMM": round(depth, 2),
            "FloorWidthMM": round(floor_w, 2),
            "FloorHeightMM": round(floor_h, 2),
            "FloorAreaMM2": round(floor_area, 2),
        })

    with (args.output / "geometry_manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows_out[0].keys())
        writer.writeheader(); writer.writerows(rows_out)
    with (args.output / "design_geometry.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=PartResult.__dataclass_fields__.keys())
        writer.writeheader(); writer.writerows([r.__dict__ for r in results])

    exact = sum(r.status == "exact" for r in results)
    mapped = sum(r.svg_file is not None for r in results)
    status_counts: dict[str, int] = {}
    for result in results:
        status_counts[result.status] = status_counts.get(result.status, 0) + 1
    missing = [r.design_id for r in results if r.svg_file is None]
    # Area-balanced colour allocation, keeping every colour intact.
    tray_areas = {"A": 0.0, "B": 0.0, "C": 0.0}
    tray_colours = {"A": [], "B": [], "C": []}
    for colour, area in sorted(colour_area.items(), key=lambda item: item[1], reverse=True):
        tray = min(tray_areas, key=tray_areas.get)
        tray_colours[tray].append(colour); tray_areas[tray] += area

    report = {
        "unique_design_ids": len(design_ids),
        "mapped_design_ids": mapped,
        "exact_filename_matches": exact,
        "mapping_status_counts": status_counts,
        "missing_design_ids": missing,
        "offset_mm_per_side": OFFSET_MM,
        "inventory_rows": len(inventory),
        "inventory_pieces": sum(int(row["Qty"]) for row in inventory),
        "colour_floor_area_mm2": {key: round(value, 2) for key, value in sorted(colour_area.items(), key=lambda item: item[1], reverse=True)},
        "recommended_area_balanced_trays": {tray: {"colours": tray_colours[tray], "floor_area_mm2": round(tray_areas[tray], 2)} for tray in "ABC"},
        "ldraw_attribution": "Geometry derived from the LDraw Parts Library. Retain LDraw attribution and applicable license notices.",
    }
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    atlas(results, args.output / "silhouette_atlas.png")
    (args.output / "ATTRIBUTION.md").write_text(
        "# Attribution\n\nGeometry in this folder is derived from the LDraw Parts Library cloned from `pybricks/ldraw`. "
        "LDraw files remain subject to the library's own license and attribution requirements. "
        "The 0.1 mm buffered SVGs are engineering derivatives for fit testing, not official LEGO CAD.\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2), flush=True)
    if mapped < 190:
        raise SystemExit(f"Geometry coverage too low: {mapped}/{len(design_ids)}")


if __name__ == "__main__":
    main()
