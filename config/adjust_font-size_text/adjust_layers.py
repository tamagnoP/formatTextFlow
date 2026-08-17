#!/usr/bin/env python3

"""

Standardise typography across an Inkscape figure.
 
1. Sets one font family on all text
2. Sets font-size per layer according to RULES below. 

Sizes are corrected for the composed transform at each node,
regardless of how the containing group has been scaled.
 
Usage
-----
As an Inkscape extension: drop this next to its .inx in the extensions dir.
As a batch tool (set DRY_RUN = False):  python3 adjust_layers.py in.svg > out.svg
 
DRY_RUN = True changes nothing and writes ~/adjust_layers_report.txt describing
what would happen. Every run shows a one-line banner naming the version.
 
Rule matching
-------------
A layer matches a rule if the rule keyword equals the layer name, or failing
that if it appears anywhere in it. Exact beats substring; longer substring
beats shorter; ties fall back to the order the rules are declared. When more
than one rule matches, the report says so rather than silently picking.
"""
 
import os
import re
from datetime import datetime
 
import inkex
from inkex import TextElement, Tspan, Layer
 
VERSION = "v5"
DRY_RUN = False
REPORT_PATH = os.path.expanduser(f"~/adjust_layers_report{datetime.now()}.txt")
 
# Inkscape's flowed text (click-drag text boxes). Not produced by matplotlib
# exports, but easy to introduce by hand later, so handle it if inkex knows it.
FlowRoot = getattr(inkex, "FlowRoot", None)
FlowPara = getattr(inkex, "FlowPara", None)
FlowSpan = getattr(inkex, "FlowSpan", None)
 
# Elements that own a font-family: family + size are set on these.
CONTAINERS = tuple(c for c in (TextElement, FlowRoot) if c is not None)
# Elements that should inherit the family from their container: size only.
CHILDREN = tuple(c for c in (Tspan, FlowPara, FlowSpan) if c is not None)
TEXT_TYPES = CONTAINERS + CHILDREN
 
ABSOLUTE_UNITS = {
    "": 1.0,
    "px": 1.0,
    "pt": 4.0 / 3.0,
    "pc": 16.0,
    "in": 96.0,
    "cm": 96.0 / 2.54,
    "mm": 96.0 / 25.4,
    "Q": 96.0 / 101.6,
}
 
LENGTH_RE = re.compile(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*([a-zA-Z%]*)\s*$")
 
 
def absolute_user_units(value):
    """Length in user units, or None if the value is missing or relative."""
    if value is None:
        return None
    match = LENGTH_RE.match(str(value))
    if not match:
        return None
    number, unit = match.groups()
    if unit not in ABSOLUTE_UNITS:
        return None
    return float(number) * ABSOLUTE_UNITS[unit]
 
 
def px(value):
    """Format a user-unit length without exponents or float noise."""
    return "{:f}".format(round(value, 4)).rstrip("0").rstrip(".") + "px"
 
 
def drop_attrib(element, name):
    if name in element.attrib:
        del element.attrib[name]
 
 
class AdjustFontLayers(inkex.EffectExtension):
 
    FONT_FAMILY = "Arial"
    FONT_SPEC = "Arial"
 
    # Layer keyword -> target size, as it should appear on the printed page.
    RULES = {
        "panel": "12pt",
        "label": "8pt",
        "ticks": "7pt",
        "scale": "6pt",
        "stats": "6pt"
    }
 
    # Divide the target by the composed transform scale, so the rendered size
    # is the requested one regardless of how the group has been scaled.
    COMPENSATE_TRANSFORMS = True
 
    # Leave tspans carrying a relative size or a baseline shift alone, so
    # super/subscripts keep their proportion.
    PRESERVE_RELATIVE_TSPANS = True
 
    # Warn when a node's x and y scales differ by more than this fraction.
    ANISOTROPY_TOLERANCE = 0.02
 
    def has_changed(self, ret):
        """Always write when applying, never when dry-running.
 
        Inkscape's default is to skip the write when the document is
        byte-identical, which is right for a dry run but leaves an empty file
        when batch-processing an already-correct figure from the shell.
        """
        return not DRY_RUN
 
    def effect(self):
        self.pt_unit = self.svg.unittouu("1pt")  # user units per point
        rows = []
        layer_counts = {}
        ambiguous = {}
        skewed = {}
        changed = untouched = 0
 
        for element in self.svg.descendants():
            if not isinstance(element, TEXT_TYPES):
                continue
 
            record = self.plan(element)
            rows.append(self.format_record(record))
            layer_counts[record["layer"]] = layer_counts.get(record["layer"], 0) + 1
 
            if len(record["matches"]) > 1:
                ambiguous[record["layer"]] = record["matches"]
            if record["skew"]:
                skewed.setdefault(record["skew"], []).append(record["id"])
 
            if record["after"] != record["before"]:
                changed += 1
            else:
                untouched += 1
            if not DRY_RUN:
                self.apply(element, record)
 
        summary = "size changed: {}   size untouched: {}".format(changed, untouched)
        self.write_report(rows, layer_counts, ambiguous, skewed, summary)
 
    # ------------------------------------------------------------- decisions
 
    def match_rule(self, label):
        """Return (chosen keyword, all matching keywords) for a layer name."""
        name = (label or "").strip().lower()
        if not name:
            return None, []
        order = list(self.RULES)
        matches = [key for key in order if key in name]
        if not matches:
            return None, []
        exact = [key for key in matches if key == name]
        if exact:
            return exact[0], matches
        chosen = sorted(matches, key=lambda key: (-len(key), order.index(key)))[0]
        return chosen, matches
 
    def plan(self, element):
        style = element.style
        layer = self.closest_layer(element)
        label = (layer.label or "") if layer is not None else ""
        scale, skew = self.composed_scale(element)
        keyword, matches = self.match_rule(label)
 
        target = None
        if keyword is not None:
            target = self.svg.unittouu(self.RULES[keyword])
            if self.COMPENSATE_TRANSFORMS and scale:
                target = target / scale
 
        before = style.get("font-size") or element.get("font-size")
        after = before
 
        if target is None:
            reason = "unmapped - left as authored"
        elif self.skip_size(element, style):
            reason = "matched '{}' but relative - kept".format(keyword)
        else:
            after = px(target)
            reason = "matched '{}' -> {}".format(keyword, self.RULES[keyword])
 
        return {
            "id": element.get("id") or "-",
            "tag": element.tag.split("}")[-1],
            "layer": label or "(no layer)",
            "scale": scale,
            "skew": skew,
            "before": before,
            "after": after,
            "reason": reason,
            "matches": matches,
        }
 
    def apply(self, element, record):
        style = element.style
        if record["after"] != record["before"] and record["after"] is not None:
            style["font-size"] = record["after"]
            drop_attrib(element, "font-size")
 
        if isinstance(element, CONTAINERS):
            style["font-family"] = self.FONT_FAMILY
            style["-inkscape-font-specification"] = self.FONT_SPEC
        else:
            # Inherit the family from the containing text element.
            style.pop("font-family", None)
            style.pop("-inkscape-font-specification", None)
        drop_attrib(element, "font-family")
 
        element.style = style
 
    def skip_size(self, element, style):
        if not (self.PRESERVE_RELATIVE_TSPANS and isinstance(element, CHILDREN)):
            return False
        if "baseline-shift" in style:
            return True
        current = style.get("font-size") or element.get("font-size")
        return current is not None and absolute_user_units(current) is None
 
    def composed_scale(self, element):
        """Uniform scale applied to this node by all its ancestors.
 
        Rotation-invariant. Returns (scale, skew description or '').
        """
        try:
            matrix = element.composed_transform().matrix
        except Exception as exc:  # pragma: no cover - defensive
            return None, "no composed transform ({})".format(exc)
        (a, c, _), (b, d, _) = matrix
        sx = (a * a + b * b) ** 0.5
        sy = (c * c + d * d) ** 0.5
        if not sx or not sy:
            return None, "degenerate transform"
        skew = ""
        spread = abs(sx - sy) / max(sx, sy)
        if spread > self.ANISOTROPY_TOLERANCE:
            skew = "sx={:.4f} sy={:.4f} ({:.1f}% stretch)".format(sx, sy, spread * 100)
        return (sx * sy) ** 0.5, skew
 
    @staticmethod
    def closest_layer(element):
        """Nearest ancestor layer. A plain <g> does not shield its contents."""
        node = element.getparent()
        while node is not None:
            if isinstance(node, Layer):
                return node
            node = node.getparent()
        return None
 
    # --------------------------------------------------------------- report
 
    def as_pt(self, value, scale):
        """On-page size in points for a font-size in local user units."""
        size = absolute_user_units(value)
        if size is None or not self.pt_unit:
            return None
        return size * (scale if scale else 1.0) / self.pt_unit
 
    def format_record(self, record):
        scale = record["scale"]
        before_pt = self.as_pt(record["before"], scale)
        after_pt = self.as_pt(record["after"], scale)
        flag = ""
        if before_pt and after_pt and not 0.67 < (after_pt / before_pt) < 1.5:
            flag = "!!"
        show = lambda v: "{:.2f}pt".format(v) if v is not None else "-"
        return "{:<3}{:<16}{:<6}{:<14}{:<8}{:<12}{:<12}{:<9}{:<9}{}".format(
            flag,
            record["id"][:15],
            record["tag"][:5],
            record["layer"][:13],
            "{:.4f}".format(scale) if scale else "-",
            str(record["before"]),
            str(record["after"]),
            show(before_pt),
            show(after_pt),
            record["reason"],
        )
 
    def write_report(self, rows, layer_counts, ambiguous, skewed, summary):
        svg = self.svg
        lines = [
            "adjust_layers {} - {}".format(
                VERSION, "DRY RUN" if DRY_RUN else "APPLYING CHANGES"),
            "width={}  height={}  viewBox={}".format(
                svg.get("width"), svg.get("height"), svg.get("viewBox")),
            "1pt = {} user units".format(round(self.pt_unit, 6)),
            "transform compensation: {}".format(
                "ON" if self.COMPENSATE_TRANSFORMS else "OFF"),
        ]
        for keyword, size in self.RULES.items():
            lines.append("  rule '{}' {} = {} user units at scale 1".format(
                keyword, size, px(svg.unittouu(size))))
        lines += [
            "",
            "'renders' and 'will be' are on-page pt. Those are the numbers that matter;",
            "raw font-size values are not comparable across differently scaled groups.",
            "'!!' marks an on-page change larger than 1.5x in either direction.",
            "",
            "{:<3}{:<16}{:<6}{:<14}{:<8}{:<12}{:<12}{:<9}{:<9}{}".format(
                "", "id", "tag", "layer", "scale", "before", "after",
                "renders", "will be", "reason"),
        ]
        lines += rows
 
        lines += ["", "text nodes per layer:"]
        for name, count in sorted(layer_counts.items(), key=lambda kv: -kv[1]):
            lines.append("  {:<28} {}".format(name, count))
 
        if ambiguous:
            lines += ["", "layers matching more than one rule:"]
            for name, matches in sorted(ambiguous.items()):
                chosen, _ = self.match_rule(name)
                lines.append("  '{}' matches {} - using '{}'".format(
                    name, ", ".join(repr(m) for m in matches), chosen))
 
        if skewed:
            lines += ["", "non-uniform scaling (glyphs are stretched):"]
            for description, ids in sorted(skewed.items(), key=lambda kv: -len(kv[1])):
                sample = ", ".join(ids[:4])
                extra = " (+{} more)".format(len(ids) - 4) if len(ids) > 4 else ""
                lines.append("  {} - {} nodes: {}{}".format(
                    description, len(ids), sample, extra))
            lines.append("  Sizes use the geometric mean, so each lands within half")
            lines.append("  the stretch of its target. Fixing the distortion itself")
            lines.append("  means correcting the offending group transform.")
 
        lines += ["", summary]
 
        try:
            with open(REPORT_PATH, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
            note = "report: " + REPORT_PATH
        except OSError as exc:
            note = "could not write report ({})".format(exc)
 
        inkex.errormsg("adjust_layers {} | {} | {} | {}".format(
            VERSION,
            "DRY RUN - nothing modified" if DRY_RUN else "changes applied",
            summary,
            note,
        ))
 
 
if __name__ == "__main__":
    AdjustFontLayers().run() 