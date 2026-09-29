"""
contributions_card.py — Render the profile's contribution stats as a psql-style
query result (SVG), from the GitHub GraphQL contribution calendar.

Env:
  GITHUB_TOKEN   token for the GraphQL API (the Actions token is enough)
  PROFILE_USER   GitHub login (defaults to the repository owner)
  CARD_OUT       output path (default dist/contributions.svg)
"""

import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone

USER = os.environ.get("PROFILE_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "arnav1803"
OUT = os.environ.get("CARD_OUT", "dist/contributions.svg")
TOKEN = os.environ["GITHUB_TOKEN"]

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    createdAt
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""


def graphql(variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    body = json.loads(urllib.request.urlopen(req, timeout=30).read())
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]["user"]


def daily_counts(today):
    """date -> contributions, for every day since the account was created."""
    counts, created_year, year = {}, None, today.year
    while created_year is None or year >= created_year:
        user = graphql({"login": USER, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"})
        created_year = created_year or int(user["createdAt"][:4])
        for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                counts[day["date"]] = day["contributionCount"]
        year -= 1
    return counts


def longest_streak(counts):
    longest = run = 0
    for d in sorted(counts):
        run = run + 1 if counts[d] else 0
        longest = max(longest, run)
    return longest


def render(cols, today):
    w, h = 820, 170
    mono = "ui-monospace, 'SFMono-Regular', 'JetBrains Mono', Menlo, Consolas, monospace"
    col_w = (w - 56) / len(cols)
    cells = []
    for i, (label, value) in enumerate(cols):
        x = 28 + i * col_w
        cells.append(f'<text x="{x + 14}" y="84" class="head">{label}</text>')
        cells.append(f'<text x="{x + 14}" y="128" class="val">{value}</text>')
        if i:
            cells.append(f'<line x1="{x}" y1="66" x2="{x}" y2="140" class="rule"/>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img"
     aria-label="{'; '.join(f'{l}: {v}' for l, v in cols)}">
<style>
  text {{ font-family: {mono}; }}
  .card {{ fill: #f7faf9; stroke: #d0d7de; }}
  .prompt {{ font-size: 15px; fill: #57606a; }}
  .prompt tspan.q {{ fill: #0f766e; font-weight: 700; }}
  .head {{ font-size: 13px; fill: #57606a; }}
  .val {{ font-size: 30px; font-weight: 700; fill: #1f2328; }}
  .rule {{ stroke: #d0d7de; }}
  .foot {{ font-size: 12px; fill: #8c959f; }}
  @media (prefers-color-scheme: dark) {{
    .card {{ fill: #0d1117; stroke: #30363d; }}
    .prompt, .head {{ fill: #8b949e; }}
    .prompt tspan.q {{ fill: #2dd4bf; }}
    .val {{ fill: #e6edf3; }}
    .rule {{ stroke: #30363d; }}
    .foot {{ fill: #6e7681; }}
  }}
</style>
<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" class="card"/>
<text x="28" y="40" class="prompt">{USER}=&gt; <tspan class="q">SELECT</tspan> * <tspan class="q">FROM</tspan> contributions_summary;</text>
<line x1="28" y1="58" x2="{w - 28}" y2="58" class="rule"/>
{chr(10).join(cells)}
<text x="28" y="{h - 12}" class="foot">(1 row) · refreshed {today.isoformat()}</text>
</svg>
"""


def main():
    today = datetime.now(timezone.utc).date()
    counts = daily_counts(today)
    counts = {d: c for d, c in counts.items() if d <= today.isoformat()}
    year_ago = (today - timedelta(days=365)).isoformat()
    last_year = [c for d, c in counts.items() if d > year_ago]
    longest = longest_streak(counts)
    cols = [
        ("total", f"{sum(counts.values()):,}"),
        ("last_365_days", f"{sum(last_year):,}"),
        ("active_days", f"{sum(1 for c in last_year if c)}"),
        ("longest_streak", f"{longest}d"),
    ]
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(cols, today))
    print(f"wrote {OUT}: {cols}")


if __name__ == "__main__":
    main()
