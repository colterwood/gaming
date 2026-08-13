"""Render docs/BIBLE.md into docs/index.html — the browsable edition.

    python tools/build_bible_html.py

Reads the generated markdown rather than the game, so there is exactly one
source of truth: change a constant, run build_bible.py, run this. The visual
identity is the game's own — the palette is lifted straight out of
config.CARD_PALETTE, which was itself sampled from real 1991 Impel Marvel
Universe card backs in assets/reference/.

Only the markdown subset build_bible.py actually emits is supported:
headings, tables, paragraphs, ordered lists, `code`, **bold**, *italic*,
[links](#anchors), <sub>, and horizontal rules.
"""

import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import config                                     # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "docs", "BIBLE.md")
# docs/ is the GitHub Pages root, so this is index.html: the project's
# front door at colterwood.github.io/gaming/.
OUT = os.path.join(HERE, "docs", "index.html")

CARD = config.CARD_PALETTE
PIXEL = config.PIXEL_PALETTE


def slug(text):
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", text).strip("-")


def inline(text):
    """Markdown inline → HTML.

    Code spans are lifted out BEFORE the emphasis passes and put back after.
    Without that, the `*` inside a span like `data/*.json` pairs with the
    next real asterisk in the paragraph and italicises everything between
    them, leaving a stray `*` on the page."""
    out = html.escape(text, quote=False)
    out = out.replace("&lt;sub&gt;", "<sub>").replace("&lt;/sub&gt;", "</sub>")

    spans = []

    def stash(match):
        spans.append(match.group(1))
        return f"\x00{len(spans) - 1}\x00"

    out = re.sub(r"`([^`]+)`", stash, out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", out)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    return re.sub(r"\x00(\d+)\x00",
                  lambda m: f"<code>{spans[int(m.group(1))]}</code>", out)


def convert(md):
    """Markdown → the body HTML, plus the section index."""
    lines = md.split("\n")
    body, index = [], []
    i = 0
    open_section = False

    while i < len(lines):
        line = lines[i]

        # --- table -------------------------------------------------------
        if line.startswith("|") and i + 1 < len(lines) and \
                set(lines[i + 1].replace("|", "").strip()) <= {"-", " "}:
            headers = [c.strip() for c in line.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            body.append('<div class="scroll"><table>')
            body.append("<thead><tr>" + "".join(
                f"<th>{inline(c)}</th>" for c in headers) + "</tr></thead>")
            body.append("<tbody>")
            for row in rows:
                cells = "".join(f"<td>{inline(c)}</td>" for c in row)
                body.append(f"<tr>{cells}</tr>")
            body.append("</tbody></table></div>")
            continue

        # --- headings ----------------------------------------------------
        if line.startswith("### "):
            body.append(f'<h3 id="{slug(line[4:])}">{inline(line[4:])}</h3>')
        elif line.startswith("## "):
            title = line[3:]
            if open_section:
                body.append("</section>")
            anchor = slug(title)
            number, _, label = title.partition(". ")
            body.append(f'<section id="{anchor}">')
            open_section = True
            if label:
                body.append(
                    f'<h2><span class="num">{html.escape(number)}</span>'
                    f'<span class="ttl">{inline(label)}</span></h2>')
                index.append((number, label, anchor))
            else:
                body.append(f'<h2><span class="ttl">{inline(title)}</span></h2>')
        elif line.startswith("# "):
            pass                                    # the masthead is authored
        # --- rules, lists, prose -----------------------------------------
        elif line.strip() == "---":
            body.append("<hr>")
        elif re.match(r"^\d+\. ", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                items.append(f"<li>{inline(lines[i].split('. ', 1)[1])}</li>")
                i += 1
            body.append("<ol class=\"toc\">" + "".join(items) + "</ol>")
            continue
        elif line.strip():
            body.append(f"<p>{inline(line)}</p>")

        i += 1

    if open_section:
        body.append("</section>")
    return "\n".join(body), index


def build():
    md = open(SRC, encoding="utf-8").read()
    body, index = convert(md)
    # The masthead line and the standfirst come from the markdown itself.
    glance = next(l for l in md.split("\n") if l.startswith("**At a glance:**"))
    counts = glance.split("**At a glance:**")[1].strip().split(" · ")

    rail = "\n".join(
        f'<li><a href="#{a}"><span class="n">{n}</span>'
        f'<span>{html.escape(t)}</span></a></li>' for n, t, a in index)
    chips = "\n".join(
        f'<li><b>{html.escape(c.split(" ", 1)[0])}</b> '
        f'{html.escape(c.split(" ", 1)[1])}</li>' for c in counts)

    page = TEMPLATE.format(card=CARD, pixel=PIXEL, rail=rail, chips=chips,
                           body=body)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {OUT}  ({len(page) // 1024} KB)")


TEMPLATE = """<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Roads to Secret Wars — The Bible</title>
<style>
:root {{
  --paper:   {card[cream]};
  --card:    {card[paper]};
  --banner:  {card[yellow]};
  --blue:    {card[blue]};
  --bar:     {card[bar_pink]};
  --strip:   {card[red]};
  --ink:     #17131d;
  --muted:   #5d5647;
  --rule:    #cabfa6;
  --sunk:    #e6dcc4;
  --shadow:  rgba(23,19,29,.13);
  --dot:     rgba(23,19,29,.10);
  --display: Haettenschweiler, "Arial Narrow Bold", "Franklin Gothic Heavy",
             Impact, "Anton", sans-serif;
  --body:    ui-sans-serif, system-ui, "Segoe UI", Roboto, Helvetica, Arial,
             sans-serif;
  --mono:    ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas,
             monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --paper:  {pixel[ink]};
    --card:   {pixel[shadow]};
    --banner: {pixel[gold]};
    --blue:   {pixel[sky]};
    --bar:    {pixel[pink]};
    --strip:  {pixel[red]};
    --ink:    {pixel[paper]};
    --muted:  {pixel[steel]};
    --rule:   {pixel[steel_dark]};
    --sunk:   #211c2c;
    --shadow: rgba(0,0,0,.5);
    --dot:    rgba(255,253,245,.05);
  }}
}}
:root[data-theme="dark"] {{
  --paper:  {pixel[ink]};
  --card:   {pixel[shadow]};
  --banner: {pixel[gold]};
  --blue:   {pixel[sky]};
  --bar:    {pixel[pink]};
  --strip:  {pixel[red]};
  --ink:    {pixel[paper]};
  --muted:  {pixel[steel]};
  --rule:   {pixel[steel_dark]};
  --sunk:   #211c2c;
  --shadow: rgba(0,0,0,.5);
  --dot:    rgba(255,253,245,.05);
}}

* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--paper);
  background-image: radial-gradient(var(--dot) 1px, transparent 1px);
  background-size: 7px 7px;
  color: var(--ink);
  font: 16px/1.6 var(--body);
  -webkit-font-smoothing: antialiased;
}}

/* ---- masthead: the card's yellow name banner ---- */
header.mast {{
  background: var(--banner);
  border-bottom: 3px solid var(--ink);
  padding: 26px clamp(16px, 4vw, 48px) 20px;
}}
.mast h1 {{
  margin: 0;
  font-family: var(--display);
  font-size: clamp(34px, 7vw, 68px);
  line-height: .92;
  letter-spacing: .01em;
  text-transform: uppercase;
  color: var(--blue);
  text-wrap: balance;
}}
/* On the gold banner the link-blue would be near-illegible in the dark
   palette, so the banner keeps ink lettering there — the banner is the one
   surface that does not flip with the theme. */
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) .mast h1 {{ color: #14100a; }}
}}
:root[data-theme="dark"] .mast h1 {{ color: #14100a; }}
.mast .sub {{
  margin: 8px 0 0;
  max-width: 62ch;
  color: #3a3320;
  font-size: 14.5px;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) .mast .sub {{ color: #4a3d05; }}
}}
:root[data-theme="dark"] .mast .sub {{ color: #4a3d05; }}
.mast .sub code {{ background: rgba(0,0,0,.09); }}

.ways {{
  display: flex; flex-wrap: wrap; gap: 4px 20px;
  margin: 14px 0 0; max-width: none;
}}
.ways a {{
  color: #14100a; font-size: 13px; font-weight: 600;
  text-decoration-thickness: 2px; text-underline-offset: 3px;
}}
.ways a:hover {{ text-decoration-color: {card[red]}; }}
.ways a:focus-visible {{ outline: 2px solid #14100a; outline-offset: 3px; }}

ul.chips {{
  display: flex; flex-wrap: wrap; gap: 6px 8px;
  list-style: none; margin: 16px 0 0; padding: 0;
}}
ul.chips li {{
  background: var(--paper); color: var(--ink);
  border: 1.5px solid var(--ink);
  padding: 2px 9px; font-size: 12px;
  font-variant-numeric: tabular-nums;
}}
ul.chips b {{ font-family: var(--mono); }}

/* ---- shell ---- */
.shell {{
  display: grid; grid-template-columns: 232px minmax(0,1fr);
  gap: clamp(20px, 3vw, 44px);
  max-width: 1240px; margin: 0 auto;
  padding: 28px clamp(16px, 4vw, 48px) 96px;
  align-items: start;
}}
@media (max-width: 900px) {{ .shell {{ grid-template-columns: 1fr; }} }}

nav.rail {{ position: sticky; top: 18px; }}
@media (max-width: 900px) {{ nav.rail {{ position: static; }} }}
.finder {{
  width: 100%; padding: 9px 11px; margin-bottom: 14px;
  background: var(--card); color: var(--ink);
  border: 2px solid var(--ink); border-radius: 0;
  font: 13px var(--body);
}}
.finder::placeholder {{ color: var(--muted); }}
.finder:focus-visible {{ outline: 3px solid var(--bar); outline-offset: 1px; }}
nav.rail ol {{ list-style: none; margin: 0; padding: 0; }}
nav.rail a {{
  display: flex; gap: 9px; align-items: baseline;
  padding: 3px 7px; text-decoration: none; color: var(--ink);
  font-size: 13.5px; border-left: 3px solid transparent;
}}
nav.rail a:hover {{ background: var(--sunk); }}
nav.rail a.on {{ border-left-color: var(--strip); background: var(--sunk); }}
nav.rail .n {{
  font-family: var(--mono); font-size: 11px; color: var(--muted);
  min-width: 1.5em; text-align: right; font-variant-numeric: tabular-nums;
}}
nav.rail a:focus-visible {{ outline: 2px solid var(--bar); }}

/* ---- content ---- */
main {{ min-width: 0; }}
section {{
  background: var(--card);
  border: 2px solid var(--ink);
  box-shadow: 4px 4px 0 var(--shadow);
  padding: 0 clamp(14px, 2.4vw, 30px) 26px;
  margin-bottom: 26px;
}}
h2 {{
  display: flex; align-items: baseline; gap: 12px;
  margin: 0 clamp(-14px, -2.4vw, -30px) 20px;
  padding: 9px clamp(14px, 2.4vw, 30px);
  background: var(--banner);
  border-bottom: 2px solid var(--ink);
}}
h2 .num {{
  font-family: var(--mono); font-size: 13px; font-weight: 700;
  color: #6b5a00; letter-spacing: .04em;
}}
h2 .ttl {{
  font-family: var(--display); text-transform: uppercase;
  font-size: clamp(21px, 3.2vw, 30px); font-weight: 400;
  letter-spacing: .015em; color: var(--blue); line-height: 1;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) h2 .num {{ color: #4a3d05; }}
  :root:not([data-theme="light"]) h2 .ttl {{ color: #1a1508; }}
}}
:root[data-theme="dark"] h2 .num {{ color: #4a3d05; }}
:root[data-theme="dark"] h2 .ttl {{ color: #1a1508; }}

h3 {{
  margin: 30px 0 10px;
  font: 700 12.5px/1.3 var(--body);
  text-transform: uppercase; letter-spacing: .1em;
  color: var(--ink);
  padding-bottom: 5px; border-bottom: 2px solid var(--bar);
  text-wrap: balance;
}}
h3:first-of-type {{ margin-top: 20px; }}

p {{ margin: 0 0 11px; max-width: 74ch; }}
p:last-child {{ margin-bottom: 0; }}
a {{ color: var(--blue); text-decoration-thickness: 1px; text-underline-offset: 2px; }}
strong {{ font-weight: 700; }}
sub {{ display: inline-block; font-size: 12px; color: var(--muted); }}
hr {{ border: 0; border-top: 2px solid var(--rule); margin: 22px 0; }}

code {{
  font: 12.5px/1.4 var(--mono);
  background: var(--sunk); padding: 1px 5px;
  border: 1px solid var(--rule);
}}

ol.toc {{
  columns: 2; column-gap: 28px;
  margin: 0; padding-left: 1.4em; font-size: 14.5px;
}}
@media (max-width: 620px) {{ ol.toc {{ columns: 1; }} }}
ol.toc li {{ break-inside: avoid; margin-bottom: 2px; }}

/* ---- tables: the power-rating grid ---- */
.scroll {{ overflow-x: auto; margin: 0 0 16px; border: 1px solid var(--rule); }}
table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; }}
th {{
  background: var(--ink); color: var(--card);
  text-align: left; padding: 6px 10px;
  font: 700 11px/1.3 var(--body);
  text-transform: uppercase; letter-spacing: .07em;
  white-space: nowrap; position: sticky; top: 0;
}}
td {{
  padding: 5px 10px; border-top: 1px solid var(--rule);
  vertical-align: top; font-variant-numeric: tabular-nums;
}}
tbody tr:nth-child(odd) {{ background: color-mix(in srgb, var(--bar) 11%, transparent); }}
tbody tr:hover {{ background: color-mix(in srgb, var(--bar) 24%, transparent); }}
td code {{ background: transparent; border: 0; padding: 0; }}
td:first-child {{ font-weight: 600; }}

.hidden {{ display: none !important; }}
.nohits {{ color: var(--muted); font-style: italic; padding: 6px 0; }}

@media print {{
  nav.rail, .finder {{ display: none; }}
  .shell {{ display: block; }}
  section {{ box-shadow: none; break-inside: avoid; }}
}}
@media (prefers-reduced-motion: reduce) {{
  * {{ animation: none !important; transition: none !important; }}
}}
</style>

<header class="mast">
  <h1>Roads to Secret Wars<br>The Bible</h1>
  <p class="sub">Every number in the game, generated from the code. Rebuild
     with <code>python tools/build_bible.py</code> then
     <code>python tools/build_bible_html.py</code>. The design narrative
     lives in GAME_SPEC.md; this is the reference sheet.</p>
  <ul class="chips">
{chips}
  </ul>
  <p class="ways">
    <a href="https://github.com/colterwood/gaming">Source on GitHub</a>
    <a href="https://github.com/colterwood/gaming/blob/main/docs/GAME_SPEC.md">Design spec</a>
    <a href="https://github.com/colterwood/gaming/blob/main/docs/BIBLE.md">Markdown edition</a>
  </p>
</header>

<div class="shell">
  <nav class="rail">
    <input class="finder" type="search" id="finder" placeholder="Filter rows…"
           aria-label="Filter every table in the document">
    <ol>
{rail}
    </ol>
  </nav>
  <main id="doc">
{body}
  </main>
</div>

<script>
(function () {{
  var finder = document.getElementById('finder');
  var sections = Array.prototype.slice.call(
    document.querySelectorAll('main section'));
  var links = Array.prototype.slice.call(
    document.querySelectorAll('nav.rail a'));

  // Filter every table row in the document, and hide sections left empty.
  finder.addEventListener('input', function () {{
    var q = finder.value.trim().toLowerCase();
    sections.forEach(function (sec) {{
      if (!q) {{
        sec.classList.remove('hidden');
        sec.querySelectorAll('tr, .scroll, h3, p, ol').forEach(function (el) {{
          el.classList.remove('hidden');
        }});
        var n = sec.querySelector('.nohits');
        if (n) {{ n.remove(); }}
        return;
      }}
      var anyRow = false;
      sec.querySelectorAll('tbody tr').forEach(function (tr) {{
        var hit = tr.textContent.toLowerCase().indexOf(q) !== -1;
        tr.classList.toggle('hidden', !hit);
        if (hit) {{ anyRow = true; }}
      }});
      // prose matches keep the section too
      var prose = sec.textContent.toLowerCase().indexOf(q) !== -1;
      sec.classList.toggle('hidden', !anyRow && !prose);
      sec.querySelectorAll('.scroll').forEach(function (box) {{
        var live = box.querySelectorAll('tbody tr:not(.hidden)').length;
        box.classList.toggle('hidden', live === 0);
      }});
    }});
  }});

  // Highlight the section you are reading.
  if ('IntersectionObserver' in window) {{
    var seen = new IntersectionObserver(function (entries) {{
      entries.forEach(function (e) {{
        if (!e.isIntersecting) {{ return; }}
        links.forEach(function (a) {{
          a.classList.toggle('on',
            a.getAttribute('href') === '#' + e.target.id);
        }});
      }});
    }}, {{ rootMargin: '-15% 0px -75% 0px' }});
    sections.forEach(function (s) {{ seen.observe(s); }});
  }}
}}());
</script>
"""


if __name__ == "__main__":
    build()
