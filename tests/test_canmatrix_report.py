import os
import tempfile

from canmatrix import report as cm_report


def test_render_html_report_includes_dynamic_assertions():
    sample_report = {
        "suite": "CAN Matrix Auto",
        "overall_pass": False,
        "summary": {
            "suite_start": "2025-12-10T10:00:00",
            "suite_end": "2025-12-10T10:00:05",
            "suite_duration_s": 5.0,
            "static_total": 2,
            "static_pass": 1,
            "dynamic_total": 2,
            "dynamic_pass": 1,
        },
        "results": [
            {
                "case_id": "ST-001",
                "passed": True,
                "log": "Static check ok",
                "assertions": [
                    {"target": "GridVol", "msg": "DLC match", "op": "==", "expected": 8, "value": 8, "passed": True}
                ],
            },
            {
                "case_id": "DYN-001",
                "passed": False,
                "log": "Dynamic check failed",
                "assertions": [
                    {
                        "target": "GridVol",
                        "msg": "Within tolerance",
                        "op": "in_range",
                        "expected": {"min": 200, "max": 250},
                        "value": 280,
                        "passed": False,
                    }
                ],
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "report.html")
        cm_report.render_html_report(sample_report, out_path)
        assert os.path.exists(out_path)
        html = open(out_path, "r", encoding="utf-8").read()
        # Header info
        assert "CAN Matrix Auto" in html
        assert "Duration" in html
        # Dynamic assertion details should appear
        assert "GridVol" in html
        assert "Within tolerance" in html
        # Summary pills should show static/dynamic counts
        assert "Static 1/2" in html
        assert "Dynamic 1/2" in html
