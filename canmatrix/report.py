import os
import datetime
import html


def render_html_report(report: dict, out_path: str):
    """Render a simple self-contained HTML report from a canmatrix run report dict."""
    suite = report.get("suite", "Suite")
    summary = report.get("summary", {})
    results = report.get("results", [])
    timestamp = datetime.datetime.now().isoformat()
    suite_pass = report.get("overall_pass", summary.get("suite_pass", False))
    badge_color = "#28a745" if suite_pass else "#dc3545"
    badge_text = "PASS" if suite_pass else "FAIL"
    dur = summary.get("suite_duration_s", None)
    dur_txt = f"{dur} s" if dur is not None else "n/a"
    started = summary.get("suite_start", "n/a")
    ended = summary.get("suite_end", "n/a")
    static_tot = summary.get("static_total", 0)
    static_pass = summary.get("static_pass", 0)
    dynamic_tot = summary.get("dynamic_total", 0)
    dynamic_pass = summary.get("dynamic_pass", 0)
    static_asserts = summary.get("static_asserts", {})
    dyn_asserts = summary.get("dynamic_asserts", {})
    static_assert_pass = static_asserts.get("passed", 0)
    static_assert_total = static_asserts.get("total", 0)
    dyn_assert_pass = dyn_asserts.get("passed", 0)
    dyn_assert_total = dyn_asserts.get("total", 0)

    def esc(s):
        return html.escape(str(s))

    rows = []
    detail_blocks = []
    for r in results:
        rows.append(
            f"<tr><td>{esc(r.get('case_id'))}</td><td>{esc(r.get('passed'))}</td>"
            f"<td>{esc(r.get('log'))}</td></tr>"
        )
        assertions = r.get("assertions", [])
        if assertions:
            a_rows = []
            for a in assertions:
                exp = a.get('expected')
                val = a.get('value')
                try:
                    if isinstance(exp, (dict, list, tuple)):
                        import json as _json
                        exp = _json.dumps(exp)
                    if isinstance(val, (dict, list, tuple)):
                        import json as _json
                        val = _json.dumps(val)
                except Exception:
                    pass
                a_rows.append(
                    f"<tr><td>{esc(a.get('target'))}</td><td>{esc(a.get('msg'))}</td>"
                    f"<td>{esc(a.get('op'))}</td><td>{esc(exp)}</td>"
                    f"<td>{esc(val)}</td><td>{esc(a.get('passed'))}</td></tr>"
                )
            detail_blocks.append(
                f"<h3>{esc(r.get('case_id'))}</h3>"
                f"<table><thead><tr><th>Target/Signal</th><th>Test</th><th>Op</th><th>Expected</th><th>Observed</th><th>Pass</th></tr></thead>"
                f"<tbody>{''.join(a_rows)}</tbody></table>"
            )
    rows_html = "\n".join(rows)
    details_html = "\n".join(detail_blocks)

    # Build progress bar segments
    def bar(percent, label):
        pct = max(0, min(100, int(percent)))
        return f"""
        <div class="bar-label">{esc(label)}: {pct}%</div>
        <div class="bar-track"><div class="bar-fill" style="width:{pct}%"></div></div>
        """

    static_assert_pct = (static_assert_pass / static_assert_total * 100) if static_assert_total else 100
    dyn_assert_pct = (dyn_assert_pass / dyn_assert_total * 100) if dyn_assert_total else 100

    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{esc(suite)} {'PASS' if suite_pass else 'FAIL'}</title>
<style>
body {{ font-family: 'Segoe UI','Helvetica Neue',Arial,sans-serif; background: #0b111a; color: #e7f1ff; margin: 0; padding: 0; }}
.container {{ max-width: 1080px; margin: 0 auto; padding: 32px 24px 48px 24px; }}
.header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #233044; padding-bottom: 12px; margin-bottom: 16px; }}
.title {{ font-size: 28px; font-weight: 700; letter-spacing: 0.5px; color: #5ce1e6; }}
.badge {{ padding: 8px 14px; border-radius: 16px; font-weight: 700; text-transform: uppercase; }}
.status-pass {{ background: #0f3c2a; color: #5df0a1; border: 1px solid #1f6c46; }}
.status-fail {{ background: #3c1f1f; color: #ff9b9b; border: 1px solid #7a2f2f; }}
.meta {{ list-style: none; padding: 0; margin: 0 0 12px 0; display: flex; flex-wrap: wrap; gap: 10px 16px; font-size: 13px; color: #9db4d4; }}
.meta li b {{ color: #e7f1ff; }}
.section-title {{ margin-top: 22px; font-size: 18px; color: #c8ddf5; }}
.pill-row {{ display: flex; gap: 10px; margin: 10px 0 4px 0; flex-wrap: wrap; }}
.pill {{ padding: 6px 12px; border-radius: 12px; font-size: 13px; font-weight: 600; border: 1px solid #1f2b3d; background: #111a26; color: #c8ddf5; }}
.pill-pass {{ border-color: #1f6c46; color: #5df0a1; }}
.pill-fail {{ border-color: #7a2f2f; color: #ff9b9b; }}
.bars {{ margin: 12px 0 8px 0; }}
.bar-label {{ font-size: 12px; color: #9db4d4; margin-bottom: 4px; }}
.bar-track {{ width: 100%; background: #0f1726; border-radius: 6px; height: 10px; border: 1px solid #1f2b3d; overflow: hidden; }}
.bar-fill {{ height: 100%; background: linear-gradient(90deg, #5ce1e6, #4aa3f0); transition: width 0.8s ease; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 12px; border: 1px solid #1f2b3d; }}
th, td {{ border: 1px solid #1f2b3d; padding: 10px; vertical-align: top; font-size: 13px; }}
th {{ background: #162133; color: #c8ddf5; text-align: left; }}
tr:nth-child(even) {{ background: #0f1726; }}
.assert-block h3 {{ margin: 16px 0 6px 0; color: #5ce1e6; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="title">{esc(suite)}</div>
      <div class="badge {'status-pass' if suite_pass else 'status-fail'}">{badge_text}</div>
    </div>
    <ul class="meta">
      <li><b>Started:</b> {esc(started)}</li>
      <li><b>Ended:</b> {esc(ended)}</li>
      <li><b>Duration:</b> {esc(dur_txt)}</li>
      <li><b>Generated:</b> {esc(timestamp)}</li>
    </ul>

    <div class="pill-row">
      <div class="pill {'pill-pass' if static_pass == static_tot else 'pill-fail'}">Static {static_pass}/{static_tot}</div>
      <div class="pill {'pill-pass' if dynamic_pass == dynamic_tot else 'pill-fail'}">Dynamic {dynamic_pass}/{dynamic_tot}</div>
    </div>

    <div class="bars">
      {bar(static_assert_pct, 'Static Assertions')}
      {bar(dyn_assert_pct, 'Dynamic Assertions')}
    </div>

    <div class="section-title">Summary</div>
    <table>
      <thead><tr><th>Metric</th><th>Value</th></tr></thead>
      <tbody>
        <tr><td>Static</td><td>{esc(summary.get('static_pass',0))} / {esc(summary.get('static_total',0))}</td></tr>
        <tr><td><b>Static Assertions</b></td><td>{esc(static_assert_pass)} / {esc(static_assert_total)}</td></tr>
        <tr><td>Dynamic</td><td>{esc(summary.get('dynamic_pass',0))} / {esc(summary.get('dynamic_total',0))}</td></tr>
        <tr><td><b>Dynamic Assertions</b></td><td>{esc(dyn_assert_pass)} / {esc(dyn_assert_total)}</td></tr>
        <tr><td>Timing</td><td>{esc(summary.get('timing_stats','n/a'))}</td></tr>
      </tbody>
    </table>

    <div class="section-title">Results</div>
    <table>
      <thead><tr><th>Case</th><th>Passed</th><th>Log</th></tr></thead>
      <tbody>
      {rows_html}
      </tbody>
    </table>

    <div class="section-title">Assertions (per case)</div>
    {details_html if details_html else '<p>No assertions recorded.</p>'}
  </div>
</body>
</html>
"""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_body)
    return out_path
