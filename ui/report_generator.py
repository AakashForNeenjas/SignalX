"""Sequence test report generator.

This module handles generation of HTML test reports from sequence execution data.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def _fmt(val: Any) -> str:
    """Format a value for display in the report."""
    if val is None:
        return ""
    try:
        if isinstance(val, (float, int)):
            return f"{val:.3f}"
    except Exception:
        pass
    return str(val)


def _mag(value: Any) -> Optional[float]:
    """Get magnitude (absolute value) of a numeric value."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return abs(value)
    try:
        return abs(float(value))
    except (TypeError, ValueError):
        return None


def _has_key(logs: List[Dict], prefix: str) -> bool:
    """Check if any log entry has a reading key starting with prefix."""
    for entry in logs:
        rd = entry.get("readings", {}) or {}
        if any(k.startswith(prefix) for k in rd.keys()):
            return True
    return False


def _has_measure(logs: List[Dict], flag: str) -> bool:
    """Check if any log entry has a measure flag set."""
    for entry in logs:
        measure = entry.get("measure", {}) or {}
        if measure.get(flag):
            return True
    return False


def _build_ramp_sections(steps: List[Dict]) -> List[str]:
    """Build HTML sections for ramp test results."""
    ramp_sections = []

    for s in steps:
        logs = s.get("ramp_logs")
        if not logs:
            continue

        has_gs = _has_key(logs, "gs_") or _has_measure(logs, "gs")
        has_ps = _has_key(logs, "ps_") or _has_measure(logs, "ps")
        has_load = _has_key(logs, "load_") or _has_measure(logs, "load")

        header_cols = ["Set Value", "Status", "Message"]
        if has_gs:
            header_cols.extend(["GS V", "GS I", "GS P", "PF", "ITHD", "VTHD", "Freq"])
        if has_ps:
            header_cols.extend(["PS V", "PS I", "PS P"])
        if has_load:
            header_cols.extend(["Load V", "Load I", "Load P"])
        if has_gs and (has_ps or has_load):
            header_cols.append("Efficiency (%)")
        header_cols.append("Errors")

        header = "<table><thead><tr>" + "".join([f"<th>{c}</th>" for c in header_cols]) + "</tr></thead><tbody>"
        body_rows = []

        for entry in logs:
            rd = entry.get("readings", {}) or {}
            errs = []
            for k in ("gs_error", "ps_error", "load_error"):
                if rd.get(k):
                    errs.append(rd[k])
            try:
                gs_p = _mag(rd.get("gs_power"))
                ps_p = _mag(rd.get("ps_power"))
                load_p = _mag(rd.get("load_power"))
                total_out = 0.0
                if ps_p is not None:
                    total_out += ps_p
                if load_p is not None:
                    total_out += load_p
                eff = (total_out / gs_p * 100.0) if gs_p is not None and gs_p != 0 and total_out is not None else None
            except Exception:
                eff = None

            body_rows.append(
                "<tr>"
                f"<td>{_fmt(entry.get('value'))}</td>"
                f"<td>{entry.get('status','')}</td>"
                f"<td>{entry.get('message','')}</td>"
                + (
                    f"<td>{_fmt(rd.get('gs_voltage'))}</td>"
                    f"<td>{_fmt(rd.get('gs_current'))}</td>"
                    f"<td>{_fmt(rd.get('gs_power'))}</td>"
                    f"<td>{_fmt(rd.get('gs_pf'))}</td>"
                    f"<td>{_fmt(rd.get('gs_ithd'))}</td>"
                    f"<td>{_fmt(rd.get('gs_vthd'))}</td>"
                    f"<td>{_fmt(rd.get('gs_freq'))}</td>"
                    if has_gs else ""
                )
                + (
                    f"<td>{_fmt(rd.get('ps_voltage'))}</td>"
                    f"<td>{_fmt(rd.get('ps_current'))}</td>"
                    f"<td>{_fmt(rd.get('ps_power'))}</td>"
                    if has_ps else ""
                )
                + (
                    f"<td>{_fmt(rd.get('load_voltage'))}</td>"
                    f"<td>{_fmt(rd.get('load_current'))}</td>"
                    f"<td>{_fmt(rd.get('load_power'))}</td>"
                    if has_load else ""
                )
                + (f"<td>{_fmt(eff)}</td>" if has_gs and (has_ps or has_load) else "")
                + f"<td>{' | '.join(errs) if errs else ''}</td>"
                + "</tr>"
            )

        section = (
            f"<div class='section'><h3>Step {s.get('index')} - {s.get('action','')}</h3>"
            f"{header}{''.join(body_rows)}</tbody></table></div>"
        )
        ramp_sections.append(section)

    return ramp_sections


def _build_short_cycle_sections(steps: List[Dict]) -> List[str]:
    """Build HTML sections for short circuit cycle test results."""
    short_cycle_sections = []

    for s in steps:
        logs = s.get("short_cycle_logs")
        if not logs:
            continue

        has_gs = False
        for entry in logs:
            rd = entry.get("readings", {}) or {}
            if any(k.startswith("gs_") for k in rd.keys()):
                has_gs = True
                break

        header_cols = [
            "Cycle", "Status", "Message", "Timestamp",
            "Pulse Set (s)", "Pulse Actual (s)",
            "Input Delay Set (s)", "Input Delay Actual (s)",
            "Post-Pulse Wait Set (s)", "Post-Pulse Wait Actual (s)",
            "Dwell Set (s)", "Dwell Actual (s)",
            "PS ON (s)", "PS OFF (s)", "PS Reset OFF (s)", "PS Reset ON (s)", "Cycle Total (s)",
            *(["GS V", "GS I", "GS P", "PF", "Freq"] if has_gs else []),
            "PS V", "PS I", "PS P",
            "Load V", "Load I", "Load P",
            "Errors",
        ]
        header = "<table><thead><tr>" + "".join([f"<th>{c}</th>" for c in header_cols]) + "</tr></thead><tbody>"
        body_rows = []

        for entry in logs:
            timing = entry.get("timing", {}) or {}
            rd = entry.get("readings", {}) or {}
            errs = entry.get("errors", []) or []
            body_rows.append(
                "<tr>"
                f"<td>{entry.get('cycle')}</td>"
                f"<td>{entry.get('status','')}</td>"
                f"<td>{entry.get('message','')}</td>"
                f"<td>{entry.get('timestamp','')}</td>"
                f"<td>{_fmt(timing.get('pulse_set_s'))}</td>"
                f"<td>{_fmt(timing.get('pulse_actual_s'))}</td>"
                f"<td>{_fmt(timing.get('input_on_delay_set_s'))}</td>"
                f"<td>{_fmt(timing.get('input_on_delay_actual_s'))}</td>"
                f"<td>{_fmt(timing.get('post_pulse_wait_set_s'))}</td>"
                f"<td>{_fmt(timing.get('post_pulse_wait_actual_s'))}</td>"
                f"<td>{_fmt(timing.get('dwell_set_s'))}</td>"
                f"<td>{_fmt(timing.get('dwell_actual_s'))}</td>"
                f"<td>{_fmt(timing.get('ps_on_s'))}</td>"
                f"<td>{_fmt(timing.get('ps_off_s'))}</td>"
                f"<td>{_fmt(timing.get('ps_reset_off_s'))}</td>"
                f"<td>{_fmt(timing.get('ps_reset_on_s'))}</td>"
                f"<td>{_fmt(timing.get('cycle_total_s'))}</td>"
                + (
                    f"<td>{_fmt(rd.get('gs_voltage'))}</td>"
                    f"<td>{_fmt(rd.get('gs_current'))}</td>"
                    f"<td>{_fmt(rd.get('gs_power'))}</td>"
                    f"<td>{_fmt(rd.get('gs_pf'))}</td>"
                    f"<td>{_fmt(rd.get('gs_freq'))}</td>"
                    if has_gs else ""
                )
                + (
                    f"<td>{_fmt(rd.get('ps_voltage'))}</td>"
                    f"<td>{_fmt(rd.get('ps_current'))}</td>"
                    f"<td>{_fmt(rd.get('ps_power'))}</td>"
                    f"<td>{_fmt(rd.get('load_voltage'))}</td>"
                    f"<td>{_fmt(rd.get('load_current'))}</td>"
                    f"<td>{_fmt(rd.get('load_power'))}</td>"
                    f"<td>{' | '.join(errs) if errs else ''}</td>"
                )
                + "</tr>"
            )

        section = (
            f"<div class='section'><h3>Step {s.get('index')} - {s.get('action','')}</h3>"
            f"{header}{''.join(body_rows)}</tbody></table></div>"
        )
        short_cycle_sections.append(section)

    return short_cycle_sections


def _build_line_load_sections(steps: List[Dict]) -> tuple:
    """Build HTML sections for line & load regulation test results.

    Returns:
        Tuple of (sections_html_list, plot_data_list)
    """
    line_load_sections = []
    line_load_plot_data = []

    for s in steps:
        logs = s.get("line_load_logs")
        if not logs:
            continue

        has_gs = _has_key(logs, "gs_")
        has_ps = _has_key(logs, "ps_")
        has_load = _has_key(logs, "load_")

        plot_enabled = False
        params_raw = s.get("params")
        if params_raw:
            try:
                params_obj = json.loads(params_raw) if isinstance(params_raw, str) else params_raw
                if isinstance(params_obj, dict):
                    plot_enabled = bool(params_obj.get("plot_efficiency", False))
            except Exception:
                plot_enabled = False

        header_cols = ["GS Set (V)", "PS Set (V)", "DL Set (A)", "Status", "Message", "Timestamp"]
        if has_gs:
            header_cols.extend(["GS V", "GS I", "GS P", "PF", "ITHD", "VTHD", "Freq"])
        if has_ps:
            header_cols.extend(["PS V", "PS I", "PS P"])
        if has_load:
            header_cols.extend(["Load V", "Load I", "Load P"])
        if has_gs and (has_ps or has_load):
            header_cols.append("Efficiency (%)")
        header_cols.append("Errors")

        header = "<table><thead><tr>" + "".join([f"<th>{c}</th>" for c in header_cols]) + "</tr></thead><tbody>"
        body_rows = []

        for entry in logs:
            rd = entry.get("readings", {}) or {}
            errs = []
            for k in ("gs_error", "ps_error", "load_error"):
                if rd.get(k):
                    errs.append(rd[k])
            try:
                gs_p = _mag(rd.get("gs_power"))
                ps_p = _mag(rd.get("ps_power"))
                load_p = _mag(rd.get("load_power"))
                total_out = 0.0
                if ps_p is not None:
                    total_out += ps_p
                if load_p is not None:
                    total_out += load_p
                eff = (total_out / gs_p * 100.0) if gs_p is not None and gs_p != 0 and total_out is not None else None
            except Exception:
                eff = None

            body_rows.append(
                "<tr>"
                f"<td>{_fmt(entry.get('gs_set'))}</td>"
                f"<td>{_fmt(entry.get('ps_set'))}</td>"
                f"<td>{_fmt(entry.get('dl_set'))}</td>"
                f"<td>{entry.get('status','')}</td>"
                f"<td>{entry.get('message','')}</td>"
                f"<td>{entry.get('timestamp','')}</td>"
                + (
                    f"<td>{_fmt(rd.get('gs_voltage'))}</td>"
                    f"<td>{_fmt(rd.get('gs_current'))}</td>"
                    f"<td>{_fmt(rd.get('gs_power'))}</td>"
                    f"<td>{_fmt(rd.get('gs_pf'))}</td>"
                    f"<td>{_fmt(rd.get('gs_ithd'))}</td>"
                    f"<td>{_fmt(rd.get('gs_vthd'))}</td>"
                    f"<td>{_fmt(rd.get('gs_freq'))}</td>"
                    if has_gs else ""
                )
                + (
                    f"<td>{_fmt(rd.get('ps_voltage'))}</td>"
                    f"<td>{_fmt(rd.get('ps_current'))}</td>"
                    f"<td>{_fmt(rd.get('ps_power'))}</td>"
                    if has_ps else ""
                )
                + (
                    f"<td>{_fmt(rd.get('load_voltage'))}</td>"
                    f"<td>{_fmt(rd.get('load_current'))}</td>"
                    f"<td>{_fmt(rd.get('load_power'))}</td>"
                    if has_load else ""
                )
                + (f"<td>{_fmt(eff)}</td>" if has_gs and (has_ps or has_load) else "")
                + f"<td>{' | '.join(errs) if errs else ''}</td>"
                + "</tr>"
            )

        plot_html = ""
        if plot_enabled:
            plot_points = []
            for entry in logs:
                rd = entry.get("readings", {}) or {}
                gs_p = _mag(rd.get("gs_power"))
                if gs_p is None:
                    gs_v = _mag(rd.get("gs_voltage"))
                    gs_i = _mag(rd.get("gs_current"))
                    if gs_v is not None and gs_i is not None:
                        gs_p = gs_v * gs_i
                ps_p = _mag(rd.get("ps_power"))
                if ps_p is None:
                    ps_v = _mag(rd.get("ps_voltage"))
                    ps_i = _mag(rd.get("ps_current"))
                    if ps_v is not None and ps_i is not None:
                        ps_p = ps_v * ps_i
                load_p = _mag(rd.get("load_power"))
                if load_p is None:
                    ld_v = _mag(rd.get("load_voltage"))
                    ld_i = _mag(rd.get("load_current"))
                    if ld_v is not None and ld_i is not None:
                        load_p = ld_v * ld_i
                if gs_p is None or gs_p == 0:
                    continue
                total_out = 0.0
                if ps_p is not None:
                    total_out += ps_p
                if load_p is not None:
                    total_out += load_p
                if total_out == 0.0:
                    continue
                # gs_p is guaranteed to be non-None and non-zero here
                eff = (total_out / gs_p) * 100.0
                plot_points.append({
                    "gs": entry.get("gs_set"),
                    "ps": entry.get("ps_set"),
                    "dl": entry.get("dl_set"),
                    "eff": eff,
                })
            plot_id = f"line-load-plot-{s.get('index')}"
            line_load_plot_data.append({"id": plot_id, "points": plot_points})
            plot_html = (
                "<div class='plot-grid' id='{pid}'>"
                "<div class='plot-card'>"
                "<div class='plot-title'>Efficiency vs GS/PS/DL (combined)</div>"
                "<canvas id='{pid}-combo' width='900' height='260'></canvas>"
                "<div class='plot-tooltip' id='{pid}-combo-tip'></div>"
                "</div>"
                "<div class='plot-card'>"
                "<div class='plot-title'>Efficiency vs PS Voltage</div>"
                "<canvas id='{pid}-ps' width='900' height='260'></canvas>"
                "<div class='plot-tooltip' id='{pid}-ps-tip'></div>"
                "</div>"
                "<div class='plot-card'>"
                "<div class='plot-title'>Efficiency vs GS Voltage</div>"
                "<canvas id='{pid}-gs' width='900' height='260'></canvas>"
                "<div class='plot-tooltip' id='{pid}-gs-tip'></div>"
                "</div>"
                "<div class='plot-card'>"
                "<div class='plot-title'>Efficiency vs DL Current</div>"
                "<canvas id='{pid}-dl' width='900' height='260'></canvas>"
                "<div class='plot-tooltip' id='{pid}-dl-tip'></div>"
                "</div>"
                "</div>"
            ).format(pid=plot_id)

        section = (
            f"<div class='section'><h3>Step {s.get('index')} - {s.get('action','')}</h3>"
            f"{plot_html}"
            f"{header}{''.join(body_rows)}</tbody></table></div>"
        )
        line_load_sections.append(section)

    return line_load_sections, line_load_plot_data


def _get_plot_script(line_load_plot_data: List[Dict]) -> str:
    """Generate JavaScript for interactive efficiency plots."""
    if not line_load_plot_data:
        return ""

    try:
        plot_payload = {
            item["id"]: item["points"]
            for item in line_load_plot_data
            if item.get("points")
        }
    except Exception:
        plot_payload = {}

    if not plot_payload:
        return ""

    return """
<script>
const lineLoadPlotData = __PLOT_DATA__;
function renderScatter(canvasId, points, xKey, xLabel, tipId) {
  const canvas = document.getElementById(canvasId);
  const tip = document.getElementById(tipId);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  const usable = points.filter(p => typeof p[xKey] === "number" && typeof p.eff === "number");
  if (!usable.length) {
    ctx.fillStyle = "#9db4d4";
    ctx.font = "12px Segoe UI, Arial";
    ctx.fillText("No plot data", 12, 20);
    return;
  }
  const xs = usable.map(p => p[xKey]);
  const ys = usable.map(p => p.eff);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const padL = 40, padR = 16, padT = 16, padB = 32;
  const xSpan = (xMax - xMin) || 1;
  const ySpan = (yMax - yMin) || 1;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;
  ctx.strokeStyle = "#233044";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padL, padT);
  ctx.lineTo(padL, h - padB);
  ctx.lineTo(w - padR, h - padB);
  ctx.stroke();
  ctx.fillStyle = "#9db4d4";
  ctx.font = "10px Segoe UI, Arial";
  ctx.fillText(xLabel, padL, h - 6);
  ctx.save();
  ctx.translate(12, h - padB);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("Efficiency (%)", 0, 0);
  ctx.restore();
  const pointsPx = [];
  for (const p of usable) {
    const x = padL + ((p[xKey] - xMin) / xSpan) * plotW;
    const y = (h - padB) - ((p.eff - yMin) / ySpan) * plotH;
    pointsPx.push({ x, y, data: p });
    ctx.fillStyle = "#5ce1e6";
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fill();
  }
  canvas.onmousemove = (evt) => {
    const mx = evt.offsetX;
    const my = evt.offsetY;
    let hit = null;
    let best = 9999;
    for (const p of pointsPx) {
      const dx = p.x - mx;
      const dy = p.y - my;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 8 && dist < best) {
        best = dist;
        hit = p;
      }
    }
    if (hit && tip) {
      const d = hit.data;
      const eff = typeof d.eff === "number" ? d.eff.toFixed(2) : "n/a";
      tip.innerHTML = `Eff: ${eff}%<br>PSV: ${d.ps}<br>GSV: ${d.gs}<br>DLI: ${d.dl}`;
      tip.style.left = `${mx + 10}px`;
      tip.style.top = `${my + 10}px`;
      tip.style.display = "block";
    } else if (tip) {
      tip.style.display = "none";
    }
  };
  canvas.onmouseleave = () => {
    if (tip) tip.style.display = "none";
  };
}
function renderCombined(canvasId, points, tipId) {
  const canvas = document.getElementById(canvasId);
  const tip = document.getElementById(tipId);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  const series = [
    { key: "gs", label: "GS V", color: "#5ce1e6" },
    { key: "ps", label: "PS V", color: "#f6c343" },
    { key: "dl", label: "DL I", color: "#ff8f8f" },
  ];
  const usable = [];
  for (const s of series) {
    const pts = points.filter(p => typeof p[s.key] === "number" && typeof p.eff === "number");
    if (pts.length) usable.push({ series: s, points: pts });
  }
  if (!usable.length) {
    ctx.fillStyle = "#9db4d4";
    ctx.font = "12px Segoe UI, Arial";
    ctx.fillText("No plot data", 12, 20);
    return;
  }
  const xsAll = usable.flatMap(group => group.points.map(p => p[group.series.key]));
  const ysAll = usable.flatMap(group => group.points.map(p => p.eff));
  const xMin = Math.min(...xsAll);
  const xMax = Math.max(...xsAll);
  const yMin = Math.min(...ysAll);
  const yMax = Math.max(...ysAll);
  const padL = 40, padR = 16, padT = 16, padB = 32;
  const xSpan = (xMax - xMin) || 1;
  const ySpan = (yMax - yMin) || 1;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;
  ctx.strokeStyle = "#233044";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padL, padT);
  ctx.lineTo(padL, h - padB);
  ctx.lineTo(w - padR, h - padB);
  ctx.stroke();
  ctx.fillStyle = "#9db4d4";
  ctx.font = "10px Segoe UI, Arial";
  ctx.fillText("Value", padL, h - 6);
  ctx.save();
  ctx.translate(12, h - padB);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("Efficiency (%)", 0, 0);
  ctx.restore();
  const pointsPx = [];
  for (const group of usable) {
    ctx.fillStyle = group.series.color;
    for (const p of group.points) {
      const x = padL + ((p[group.series.key] - xMin) / xSpan) * plotW;
      const y = (h - padB) - ((p.eff - yMin) / ySpan) * plotH;
      pointsPx.push({ x, y, data: p, series: group.series });
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  let legendX = w - padR - 70;
  let legendY = padT + 4;
  for (const s of series) {
    ctx.fillStyle = s.color;
    ctx.fillRect(legendX, legendY, 10, 10);
    ctx.fillStyle = "#9db4d4";
    ctx.fillText(s.label, legendX + 14, legendY + 9);
    legendY += 14;
  }
  canvas.onmousemove = (evt) => {
    const mx = evt.offsetX;
    const my = evt.offsetY;
    let hit = null;
    let best = 9999;
    for (const p of pointsPx) {
      const dx = p.x - mx;
      const dy = p.y - my;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 8 && dist < best) {
        best = dist;
        hit = p;
      }
    }
    if (hit && tip) {
      const d = hit.data;
      const eff = typeof d.eff === "number" ? d.eff.toFixed(2) : "n/a";
      const label = hit.series.label;
      const val = d[hit.series.key];
      tip.innerHTML = `${label}: ${val}<br>Eff: ${eff}%<br>PSV: ${d.ps}<br>GSV: ${d.gs}<br>DLI: ${d.dl}`;
      tip.style.left = `${mx + 10}px`;
      tip.style.top = `${my + 10}px`;
      tip.style.display = "block";
    } else if (tip) {
      tip.style.display = "none";
    }
  };
  canvas.onmouseleave = () => {
    if (tip) tip.style.display = "none";
  };
}
function renderLineLoadPlots() {
  Object.entries(lineLoadPlotData).forEach(([plotId, points]) => {
    renderCombined(`${plotId}-combo`, points, `${plotId}-combo-tip`);
    renderScatter(`${plotId}-ps`, points, "ps", "PS Voltage (V)", `${plotId}-ps-tip`);
    renderScatter(`${plotId}-gs`, points, "gs", "GS Voltage (V)", `${plotId}-gs-tip`);
    renderScatter(`${plotId}-dl`, points, "dl", "DL Current (A)", `${plotId}-dl-tip`);
  });
}
document.addEventListener("DOMContentLoaded", renderLineLoadPlots);
</script>
""".replace("__PLOT_DATA__", json.dumps(plot_payload))


def _get_report_css() -> str:
    """Get the CSS styles for the HTML report."""
    return """
body { font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; background: #0b111a; color: #e7f1ff; margin: 0; padding: 0; }
.container { max-width: 1080px; margin: 0 auto; padding: 32px 24px 48px 24px; }
.header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #233044; padding-bottom: 12px; margin-bottom: 16px; }
.title { font-size: 28px; font-weight: 700; letter-spacing: 0.5px; color: #5ce1e6; }
.badge { padding: 8px 14px; border-radius: 16px; font-weight: 700; text-transform: uppercase; }
.status-pass { background: #0f3c2a; color: #5df0a1; border: 1px solid #1f6c46; }
.status-fail { background: #3c1f1f; color: #ff9b9b; border: 1px solid #7a2f2f; }
.meta { list-style: none; padding: 0; margin: 0 0 12px 0; display: flex; flex-wrap: wrap; gap: 10px 16px; font-size: 13px; color: #9db4d4; }
.meta li b { color: #e7f1ff; }
.dates { font-size: 13px; color: #9db4d4; margin-bottom: 8px; }
table { width: 100%; border-collapse: collapse; margin-top: 16px; border: 1px solid #1f2b3d; }
th, td { border: 1px solid #1f2b3d; padding: 10px; vertical-align: top; font-size: 13px; }
th { background: #162133; color: #c8ddf5; text-align: left; }
tr:nth-child(even) { background: #0f1726; }
.plot-grid { display: grid; grid-template-columns: 1fr; gap: 18px; margin: 16px 0 22px 0; }
.plot-card { background: linear-gradient(180deg, #111a2a 0%, #0b111a 100%); border: 1px solid #233044; border-radius: 10px; padding: 12px; position: relative; box-shadow: 0 6px 18px rgba(0,0,0,0.25); }
.plot-card canvas { width: 100%; height: 260px; display: block; }
.plot-title { font-size: 13px; color: #c8ddf5; margin-bottom: 8px; letter-spacing: 0.3px; }
.plot-tooltip { position: absolute; background: #0b111a; border: 1px solid #233044; color: #e7f1ff; padding: 6px 8px; border-radius: 6px; font-size: 11px; display: none; pointer-events: none; z-index: 5; }
tr:nth-child(odd) { background: #0c141f; }
.step-pass { color: #6dffb3; font-weight: 600; }
.step-fail { color: #ff8f8f; font-weight: 600; }
.step-running { color: #f6c343; font-weight: 600; }
.section { margin-top: 18px; }
"""


def generate_sequence_report(
    report_data: Dict[str, Any],
    output_callback: Optional[Callable[[str], None]] = None,
    logger: Optional[logging.Logger] = None
) -> Optional[Path]:
    """Generate an HTML report for a sequence run.

    Args:
        report_data: Dictionary containing sequence execution data with keys:
            - name: Sequence name
            - start_time: datetime when sequence started
            - steps: List of step dictionaries
            - meta: Optional metadata dictionary
        output_callback: Optional callback to display messages (e.g., dashboard.output_log.append)
        logger: Optional logger instance

    Returns:
        Path to the generated report file, or None if no report data
    """
    if not report_data:
        return None

    end_time = datetime.now()
    start_time = report_data.get("start_time", end_time)
    steps = report_data.get("steps", [])
    overall_pass = all(s.get("status") == "Pass" for s in steps) if steps else True
    status_text = "PASS" if overall_pass else "FAIL"
    total_seconds = max(0, (end_time - start_time).total_seconds())
    total_hms = f"{int(total_seconds // 3600):02d}:{int((total_seconds % 3600)//60):02d}:{int(total_seconds % 60):02d}"
    ts_str = end_time.strftime("%Y%m%d_%H%M%S")
    seq_name = report_data.get("name", "Sequence").replace(" ", "_")
    filename = f"{seq_name}_{status_text}_{ts_str}.html"
    json_filename = f"{seq_name}_{status_text}_{ts_str}.json"
    out_dir = Path("Test Results")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    json_path = out_dir / json_filename

    # Persist structured report as JSON
    try:
        json_path.write_text(json.dumps(report_data, default=str, indent=2), encoding="utf-8")
    except Exception:
        pass

    # Build summary table rows
    rows = []
    for s in steps:
        msgs = "<br>".join(s.get("messages", [])) or "&nbsp;"
        params = s.get("params", "")
        rows.append(
            f"<tr><td>{s.get('index')}</td><td>{s.get('action','')}</td>"
            f"<td>{params}</td><td>{s.get('status','')}</td><td>{msgs}</td></tr>"
        )

    # Build specialized sections
    ramp_sections = _build_ramp_sections(steps)
    short_cycle_sections = _build_short_cycle_sections(steps)
    line_load_sections, line_load_plot_data = _build_line_load_sections(steps)

    # Build metadata
    meta = report_data.get("meta", {})
    meta_html = "".join([f"<li><b>{k.title()}:</b> {v}</li>" for k, v in meta.items() if v])

    # Build plot script
    plot_script = _get_plot_script(line_load_plot_data)

    # Assemble HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{seq_name} {status_text}</title>
<style>
{_get_report_css()}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="title">{report_data.get("name","Test Sequence")}</div>
    <div class="badge status-{status_text.lower()}">{status_text}</div>
  </div>
  <div class="dates"><b>Started:</b> {start_time} &nbsp; <b>Ended:</b> {end_time} &nbsp; <b>Total:</b> {total_hms}</div>
  <ul class="meta">{meta_html}</ul>
  <table>
    <thead><tr><th>#</th><th>Action</th><th>Parameters</th><th>Status</th><th>Messages</th></tr></thead>
    <tbody>
    {''.join(rows)}
    </tbody>
  </table>
  {'<h2>Ramp Set &amp; Measure Results</h2>' + ''.join(ramp_sections) if ramp_sections else ''}
  {'<h2>Short Circuit Cycle Results</h2>' + ''.join(short_cycle_sections) if short_cycle_sections else ''}
  {'<h2>Line &amp; Load Regulation Results</h2>' + ''.join(line_load_sections) if line_load_sections else ''}
</div>
{plot_script}
</body>
</html>"""

    # Write report
    out_path.write_text(html, encoding="utf-8")

    if output_callback:
        output_callback(f"Report saved: {out_path}")
    if logger:
        logger.info(f"Sequence report saved: {out_path}")

    return out_path
