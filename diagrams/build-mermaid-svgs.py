#!/usr/bin/env python3
"""Render diagrams/*.mmd to <name>-light.svg and <name>-dark.svg.

Where the files go:
  * locally (default): .preview/, which is git-ignored, plus .preview/index.html to view them.
  * --publish: images/, the folder the README uses. Only allowed on GitHub Actions, so the
    committed images are always produced by CI and never by a local run.

Every .mmd file in this directory is rendered with mermaid-cli once per colour theme, for use as
<picture> sources keyed on prefers-color-scheme. Diagrams that carry animation comments are
post-processed into a looping, sequenced animation: each scenario lights up its path step by step
(nodes, subgraphs and edges stay highlighted until the scenario ends) while a title names it.

Animation comments live inside the .mmd (Mermaid ignores %% lines):

    %% @timing step=0.9 hold=2.2 gap=0.8 fade=0.2      (optional, seconds)
    %% @scenario Title shown above the diagram
    %%   node USER                       highlight a node
    %%   edge USER -> SERVICE            highlight a link (Mermaid id L_USER_SERVICE_0)
    %%   edge USER -> SERVICE #1         ...the second link between the same pair
    %%   cluster SMSMMS                  highlight a subgraph
    %%   node SESSION | Line 1 | Line 2  also swap the node's label text while lit
    %%   edge SESSION -> END ended       "ended" uses the red palette instead of amber
    %% @arrow-start SERVICE -> WEBEX       arrowhead on the first node's end of a link. Mermaid can
                                           only draw that together with an arrowhead on the other end
                                           (<-->), so draw the link as --- and add the head here.

An existing image is only overwritten when the newly rendered SVG differs from it, so edits that
do not change the output (comments, whitespace, reordered declarations) leave images/ untouched.

Setup (once, and in CI): npm ci --prefix diagrams
The Mermaid CLI is installed from diagrams/package-lock.json so every machine renders with the same
Mermaid version and the same bundled font (Recursive Variable, SIL OFL 1.1, embedded in each SVG).

Usage: python3 diagrams/build-mermaid-svgs.py            (local preview)
       python3 diagrams/build-mermaid-svgs.py --publish  (CI only)
Set PUPPETEER_EXECUTABLE_PATH to use an existing Chrome instead of a downloaded one.
When CI is set (as on GitHub Actions) Chrome is launched with --no-sandbox.
"""
import argparse
import json
import os
import re
import subprocess
import tempfile
from html import escape
from pathlib import Path

DIAGRAMS = Path(__file__).parent
ROOT = DIAGRAMS.parent
PUBLISH_DIR = ROOT / "images"
PREVIEW_DIR = ROOT / ".preview"
MMDC = DIAGRAMS / "node_modules" / ".bin" / "mmdc"

TIMING = {"step": 0.9, "hold": 2.2, "gap": 0.8, "fade": 0.2}  # seconds; see @timing
# step: between consecutive steps | hold: finished path stays lit | gap: rest between scenarios
# fade: colour change duration

ACTIVE, ENDED = "active", "ended"

# handDrawnSeed makes the neo look's slightly jittered shapes identical on every render.
# htmlLabels=False draws labels as SVG text instead of HTML in <foreignObject>. HTML labels are
# sized with the render machine's font, so when the viewer's font differs the text is clipped or
# drifts off its arrow; SVG text is positioned from the centre and stays put.
# Both themes use Mermaid's bundled "Recursive Variable" font (the light theme's default). The dark
# theme defaults to Trebuchet, which was measured with a fallback font and put edge labels off-centre.
# Viewers without the font fall back to Arial; that is fine because SVG text is centre-anchored.
FONT = {"fontFamily": '"Recursive Variable", arial, sans-serif', "fontSize": "14px"}
MERMAID_COMMON = {"handDrawnSeed": 1, "flowchart": {"htmlLabels": False}, "themeVariables": FONT}

# Per-theme settings. "base" colours are read from the rendered SVG, only highlights are set here.
THEMES = {
    "light": {
        "mermaid": {**MERMAID_COMMON},
        "text": "#28253D",
        "node": {ACTIVE: {"fill": "#FFE082", "stroke": "#E65100"},
                 ENDED: {"fill": "#EF9A9A", "stroke": "#C62828"}},
        "edge": {ACTIVE: {"stroke": "#E65100", "stroke-width": "4px"},
                 ENDED: {"stroke": "#C62828", "stroke-width": "4px"}},
    },
    "dark": {
        "mermaid": {**MERMAID_COMMON, "theme": "dark", "look": "neo"},
        "text": "#E6EDF3",
        "node": {ACTIVE: {"fill": "#7A5A00", "stroke": "#FFB74D"},
                 ENDED: {"fill": "#7F1D1D", "stroke": "#FF6B6B"}},
        "edge": {ACTIVE: {"stroke": "#FFB74D", "stroke-width": "4px"},
                 ENDED: {"stroke": "#FF6B6B", "stroke-width": "4px"}},
    },
}

def parse_arrow_starts(source):
    """Edge ids named by '%% @arrow-start A -> B [#n]' comments."""
    ids = []
    for m in re.finditer(r"^\s*%%\s*@arrow-start\s+(\w+)\s*->\s*(\w+)(?:\s*#(\d+))?\s*$", source, flags=re.M):
        ids.append(f"{m.group(1)}_{m.group(2)}_{m.group(3) or 0}")
    return ids


def add_start_arrow(svg, ident):
    """Put an arrowhead at the start of a link that Mermaid drew with no start marker."""
    tag = re.search(rf'<path[^>]*id="[^"]*-L_{ident}"[^>]*>', svg)
    assert tag, f"edge {ident} not found in rendered SVG"
    marker = re.search(r'id="([^"]*pointStart-margin)"', svg)
    assert marker, "no start arrow marker in rendered SVG"
    new_tag = tag.group(0).replace("<path ", f'<path marker-start="url(#{marker.group(1)})" ', 1)
    # Mermaid pulls a path in by 4px where it draws an arrowhead; do the same at the start
    d = re.search(r' d="M([-\d.]+),([-\d.]+)L([-\d.]+),([-\d.]+)', new_tag)
    if d:
        x1, y1, x2, y2 = map(float, d.groups())
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if length > 8:
            nx, ny = x1 + (x2 - x1) * 4 / length, y1 + (y2 - y1) * 4 / length
            new_tag = new_tag.replace(d.group(0), f' d="M{nx:g},{ny:g}L{x2:g},{y2:g}', 1)
    return svg.replace(tag.group(0), new_tag, 1)


def parse_animation(source):
    """Return (timing, scenarios) parsed from the %% comments of a .mmd file."""
    timing, scenarios = dict(TIMING), []
    for raw in source.splitlines():
        line = raw.strip()
        if not line.startswith("%%"):
            continue
        body = line[2:].strip()
        if body.startswith("@timing"):
            for pair in body.split()[1:]:
                key, _, value = pair.partition("=")
                assert key in timing, f"unknown @timing key {key!r}"
                timing[key] = float(value)
        elif body.startswith("@scenario"):
            scenarios.append({"title": body[len("@scenario"):].strip(), "steps": []})
        else:
            m = re.match(r"(node|edge|cluster)\s+(.+)$", body)
            if not m:
                continue
            assert scenarios, f"step before any @scenario: {raw!r}"
            kind, rest = m.groups()
            target, *labels = [part.strip() for part in rest.split("|")]
            style = ACTIVE
            if target.split()[-1] in (ACTIVE, ENDED):
                target, style = target.rsplit(None, 1)[0], target.split()[-1]
            if kind == "edge":
                m = re.match(r"(\w+)\s*->\s*(\w+)(?:\s*#(\d+))?$", target)
                if m:
                    target = f"{m.group(1)}_{m.group(2)}_{m.group(3) or 0}"
            scenarios[-1]["steps"].append((kind, target, style, tuple(labels)))
    return timing, scenarios


def timeline(timing, scenarios):
    """Return (cycle, windows, labels, titles).

    windows: (kind, id) -> [(start, end, style)]; labels: node id -> [(start, end, lines)].
    """
    windows, labels, titles = {}, {}, []
    t = 0.0
    for sc in scenarios:
        end = t + len(sc["steps"]) * timing["step"] + timing["hold"]
        for i, (kind, ident, style, lines) in enumerate(sc["steps"]):
            start = t + i * timing["step"]
            windows.setdefault((kind, ident), []).append((start, end, style))
            if lines:
                labels.setdefault(ident, []).append((start, end, lines))
        titles.append((t, end, sc["title"]))
        t = end + timing["gap"]
    return t, windows, labels, titles


def css(props):
    return ";".join(f"{k}:{v}" for k, v in props.items())


def keyframes(name, cycle, fade, base, windows, palette):
    pct = lambda s: round(s / cycle * 100, 3)
    frames = [f"0%{{{css(base)}}}"]
    for start, end, style in windows:
        frames += [f"{pct(start)}%{{{css(base)}}}",
                   f"{pct(start + fade)}%{{{css(palette[style])}}}",
                   f"{pct(end)}%{{{css(palette[style])}}}",
                   f"{pct(end + fade)}%{{{css(base)}}}"]
    frames.append(f"100%{{{css(base)}}}")
    return f"@keyframes {name}{{{''.join(frames)}}}"


def opacity_keyframes(name, cycle, fade, windows, visible_inside):
    pct = lambda s: round(s / cycle * 100, 3)
    on, off = (1, 0) if visible_inside else (0, 1)
    frames = [f"0%{{opacity:{off}}}"]
    for start, end in windows:
        frames += [f"{pct(start)}%{{opacity:{off}}}", f"{pct(start + fade)}%{{opacity:{on}}}",
                   f"{pct(end)}%{{opacity:{on}}}", f"{pct(end + fade)}%{{opacity:{off}}}"]
    frames.append(f"100%{{opacity:{off}}}")
    return f"@keyframes {name}{{{''.join(frames)}}}"


def bases(svg):
    """Read the theme's resting colours from the rendered SVG's stylesheet."""
    node = re.search(r"\.node rect,[^{]*\{fill:([^;]+);stroke:([^;]+);", svg)
    stroke = re.search(r"\.flowchart-link\{stroke:([^;]+);", svg)
    width = re.search(r"\.edge-thickness-normal\{stroke-width:([^;]+);", svg)
    return ({"fill": node.group(1), "stroke": node.group(2)},
            {"stroke": stroke.group(1), "stroke-width": width.group(1)})


def label_base(svg):
    """Resting background colour of edge labels, read from the stylesheet."""
    m = re.search(r"\.edgeLabel rect\{[^}]*?fill:([^;}]+)", svg)
    return {"fill": m.group(1), "stroke": "transparent", "stroke-width": "0"}


def marker_base(svg):
    """Resting colour of arrowheads, read from the stylesheet."""
    m = re.search(r"\.marker\{fill:([^;}]+);stroke:([^;}]+)", svg)
    return {"fill": m.group(1), "stroke": m.group(2)}


def clone_markers(svg, ident):
    """Give an edge its own copies of its arrowhead markers so they can be coloured independently.

    Mermaid shares one <marker> between every edge, so animating it would recolour all arrowheads.
    Returns (svg, [ids of the new markers]).
    """
    tag = re.search(rf'<path[^>]*id="[^"]*-L_{ident}"[^>]*>', svg)
    assert tag, f"edge {ident} not found in rendered SVG"
    new_tag, ids = tag.group(0), []
    for attr in ("marker-start", "marker-end"):
        ref = re.search(rf'{attr}="url\(#([^)]+)\)"', tag.group(0))
        if not ref:
            continue
        old = ref.group(1)
        marker = re.search(rf'<marker id="{re.escape(old)}".*?</marker>', svg, flags=re.S)
        new = f"{old}-{ident}"
        clone = marker.group(0).replace(f'id="{old}"', f'id="{new}"', 1)
        svg = svg.replace(marker.group(0), marker.group(0) + clone, 1)
        new_tag = new_tag.replace(ref.group(0), f'{attr}="url(#{new})"')
        ids.append(new)
    return svg.replace(tag.group(0), new_tag, 1), ids


def opaque_labels(svg):
    """Mermaid draws edge label backgrounds at 50% opacity, which lets the line show through the text."""
    svg, n = re.subn(r"</style>", "#my-svg .edgeLabel rect{opacity:1;}</style>", svg, count=1)
    assert n == 1, "no <style> block found in rendered SVG"
    return svg


def cluster_base(svg, ident):
    """Cluster colours are assigned per subgraph in some looks, so prefer the per-cluster rule."""
    color = re.search(rf'id="[^"]*-{ident}"[^>]*data-color-id="(color-\d+)"', svg)
    if color:
        m = re.search(rf'data-color-id="{color.group(1)}"\]\.cluster:not\(\.swimlane\) rect\{{stroke:(#\w+);fill:(#\w+);', svg)
        return {"fill": m.group(2), "stroke": m.group(1)}
    m = re.search(r"\.cluster rect\{fill:([^;]+);stroke:([^;]+);", svg)
    return {"fill": m.group(1), "stroke": m.group(2)}


def append_to_node(svg, ident, make_fragment):
    """Append make_fragment(cx, cy) as the last child of a node's <g> so it paints above the shape.

    (cx, cy) is the centre of the node's own label, so replacement text lines up with it.
    """
    start = re.search(rf'<g class="node[^"]*" id="[^"]*-flowchart-{ident}-\d+"', svg)
    assert start, f"node {ident} not found in rendered SVG"
    pos, depth = start.start(), 0
    for tag in re.finditer(r"<g[\s>]|</g>", svg[pos:]):
        depth += 1 if tag.group().startswith("<g") else -1
        if depth == 0:
            end = pos + tag.start()
            label = re.search(r'<g class="label"[^>]*transform="translate\(([-\d.]+), ([-\d.]+)\)"[^>]*>'
                              r'\s*(?:<rect/>)?<foreignObject width="([\d.]+)" height="([\d.]+)"', svg[pos:end])
            cx, cy = 0.0, 0.0
            if label:
                x, y, w, h = map(float, label.groups())
                cx, cy = x + w / 2, y + h / 2
            return svg[:end] + make_fragment(cx, cy) + svg[end:]
    raise AssertionError(f"unbalanced <g> for node {ident}")


def render(src, theme):
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "raw.svg"
        runner = [str(MMDC)]
        conf = Path(tmp) / "mermaid.json"
        conf.write_text(json.dumps(theme["mermaid"]))
        cmd = [*runner, "-i", str(src), "-o", str(raw), "-c", str(conf), "-b", "transparent"]
        puppeteer = {}
        if os.environ.get("PUPPETEER_EXECUTABLE_PATH"):
            puppeteer["executablePath"] = os.environ["PUPPETEER_EXECUTABLE_PATH"]
        if os.environ.get("CI"):
            puppeteer["args"] = ["--no-sandbox"]  # hosted runners block Chrome's user-namespace sandbox
        if puppeteer:
            cfg = Path(tmp) / "puppeteer.json"
            cfg.write_text(json.dumps(puppeteer))
            cmd += ["-p", str(cfg)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            # Mermaid's own message names the line; the JavaScript stack trace after it is just noise
            message = [l for l in (result.stderr or result.stdout).splitlines()
                       if l.strip() and not l.lstrip().startswith(("at ", "Parser.", "Object."))]
            raise SystemExit(f"Mermaid could not render {src.name}:\n  " + "\n  ".join(message[:8]))
        return raw.read_text()


def animate(svg, theme, timing, scenarios):
    """Inject the sequenced highlight animation described by the scenarios."""
    node_base, edge_base = bases(svg)
    label_bg = label_base(svg)
    arrow_base = marker_base(svg)
    cycle, windows, labels, titles = timeline(timing, scenarios)
    fade = timing["fade"]
    run = f"{cycle}s linear infinite"
    rules, reduced = [], []

    for (kind, ident), wins in windows.items():
        name = f"hl-{kind}-{ident.lower()}"
        if kind == "edge":
            rules.append(keyframes(name, cycle, fade, edge_base, wins, theme["edge"]))
            sel = f'path[id$="-L_{ident}"]'
            # The label's background follows the line's colour so the change is visible under long text
            label_palette = {style: {"fill": theme["node"][style]["fill"], "stroke": theme["edge"][style]["stroke"],
                                     "stroke-width": "2px"} for style in theme["edge"]}
            rules.append(keyframes(f"{name}-label", cycle, fade, label_bg, wins, label_palette))
            label_sel = f'[data-id="L_{ident}"] rect.background'
            rules.append(f"{label_sel}{{animation:{name}-label {run};}}")
            reduced.append(label_sel)
            # Arrowheads (and circle / cross ends) follow the line colour too
            svg, marker_ids = clone_markers(svg, ident)
            arrow_palette = {style: {"fill": theme["edge"][style]["stroke"], "stroke": theme["edge"][style]["stroke"]}
                             for style in theme["edge"]}
            rules.append(keyframes(f"{name}-arrow", cycle, fade, arrow_base, wins, arrow_palette))
            for marker_id in marker_ids:
                marker_sel = f'marker[id="{marker_id}"] > *'
                rules.append(f"{marker_sel}{{animation:{name}-arrow {run};}}")
                reduced.append(marker_sel)
        elif kind == "cluster":
            rules.append(keyframes(name, cycle, fade, cluster_base(svg, ident), wins, theme["node"]))
            sel = f'[id$="-{ident}"].cluster > rect'
        else:
            rules.append(keyframes(name, cycle, fade, node_base, wins, theme["node"]))
            sel = (f'[id*="-flowchart-{ident}-"] .label-container, '
                   f'[id*="-flowchart-{ident}-"] .label-container > *')
        rules.append(f"{sel}{{animation:{name} {run};}}")
        reduced.append(sel)

    # Node labels that change text while lit: hide the original, fade replacement lines in
    for ident, entries in labels.items():
        key = ident.lower()
        rules.append(opacity_keyframes(f"label-{key}", cycle, fade, [(a, b) for a, b, _ in entries], False))
        rules.append(f'[id*="-flowchart-{ident}-"] > .label{{animation:label-{key} {run};}}')
        reduced.append(f'[id*="-flowchart-{ident}-"] > .label')

        def fragment(cx, cy, key=key, entries=entries):
            out = []
            for i, (a, b, lines) in enumerate(entries):
                rules.append(opacity_keyframes(f"text-{key}-{i}", cycle, fade, [(a, b)], True))
                rules.append(f".text-{key}-{i}{{opacity:0;animation:text-{key}-{i} {run};}}")
                first = -(len(lines) - 1) * 0.7  # em; lines are 1.4em apart, block centred on cy
                spans = "".join(f'<tspan x="{cx}" dy="{first if n == 0 else 1.4:g}em">{escape(t)}</tspan>'
                                for n, t in enumerate(lines))
                out.append(f'<text class="node-text text-{key}-{i}" y="{cy}" text-anchor="middle" '
                           f'dominant-baseline="central" fill="{theme["text"]}" font-size="14">{spans}</text>')
            return "".join(out)

        svg = append_to_node(svg, ident, fragment)

    # Titles: widen the viewBox upwards to make room
    vb = re.search(r'viewBox="([\d.\-]+) ([\d.\-]+) ([\d.]+) ([\d.]+)"', svg)
    x, y, w, h = map(float, vb.groups())
    pad = 44
    svg = svg.replace(vb.group(0), f'viewBox="{x} {y - pad} {w} {h + pad}"', 1)
    title_els = []
    for i, (a, b, text) in enumerate(titles):
        rules.append(opacity_keyframes(f"title-{i}", cycle, fade, [(a, b)], True))
        rules.append(f".title-{i}{{opacity:0;animation:title-{i} {run};}}")
        title_els.append(f'<text class="title title-{i}" x="{x + w / 2}" y="{y - pad + 30}" text-anchor="middle" '
                         f'fill="{theme["text"]}" font-size="20" font-weight="600">{escape(text)}</text>')
    svg = svg.replace("</svg>", "".join(title_els) + "</svg>")

    rules.append("@media (prefers-reduced-motion:reduce){"
                 + ",".join(reduced + [".node-text", ".title"]) + "{animation:none!important}"
                 ".node-text,.title{display:none}}")
    svg, n = re.subn(r"</style>", "".join(rules) + "</style>", svg, count=1)
    assert n == 1, "no <style> block found in rendered SVG"
    return svg, cycle


def build(src, variant, theme, out_dir):
    svg = opaque_labels(render(src, theme))
    for ident in parse_arrow_starts(src.read_text()):
        svg = add_start_arrow(svg, ident)
    timing, scenarios = parse_animation(src.read_text())
    note = "static"
    if scenarios:
        svg, cycle = animate(svg, theme, timing, scenarios)
        note = f"animated, cycle {cycle:.1f}s"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{src.stem}-{variant}.svg"
    name = out.relative_to(ROOT)
    if out.exists() and out.read_text() == svg:
        print(f"unchanged {name} ({note})")
        return
    out.write_text(svg)
    print(f"wrote {name} ({note})")


def write_preview_page(out_dir, sources):
    """A page that shows each diagram like the README does, so animations can be viewed locally."""
    sections = "".join(
        f'<h2>{src.stem}</h2><picture>'
        f'<source media="(prefers-color-scheme: dark)" srcset="{src.stem}-dark.svg">'
        f'<img alt="{src.stem}" src="{src.stem}-light.svg" style="max-width:100%"></picture>'
        for src in sources)
    (out_dir / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Diagram preview</title>'
        '<style>:root{color-scheme:light dark}body{font-family:sans-serif;margin:2rem}</style>'
        f"<h1>Diagram preview (local, not committed)</h1>{sections}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--publish", action="store_true",
                        help="write to images/ (GitHub Actions only)")
    args = parser.parse_args()
    if args.publish and not os.environ.get("GITHUB_ACTIONS"):
        parser.error("--publish is only allowed on GitHub Actions; images/ is generated by CI. "
                     "Run without it to preview locally in .preview/")
    out_dir = PUBLISH_DIR if args.publish else PREVIEW_DIR

    if not MMDC.exists():
        parser.error("mermaid-cli is not installed; run: npm ci --prefix diagrams")
    sources = sorted(DIAGRAMS.glob("*.mmd"))
    assert sources, f"no .mmd files in {DIAGRAMS}"
    for src in sources:
        for variant, theme in THEMES.items():
            build(src, variant, theme, out_dir)
    if not args.publish:
        write_preview_page(out_dir, sources)
        print(f"open {(out_dir / 'index.html').relative_to(ROOT)} to view the animations")


if __name__ == "__main__":
    main()
