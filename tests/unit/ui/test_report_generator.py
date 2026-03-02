"""Unit tests for report generator module."""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from ui.report_generator import (
    _fmt,
    _mag,
    _has_key,
    _has_measure,
    _build_ramp_sections,
    _build_short_cycle_sections,
    _build_line_load_sections,
    _get_plot_script,
    _get_report_css,
    generate_sequence_report,
)


@pytest.mark.unit
class TestHelperFunctions:
    """Tests for helper functions."""

    def test_fmt_none(self):
        """Test _fmt with None value."""
        assert _fmt(None) == ""

    def test_fmt_float(self):
        """Test _fmt with float value."""
        assert _fmt(3.14159) == "3.142"

    def test_fmt_int(self):
        """Test _fmt with int value."""
        assert _fmt(42) == "42.000"

    def test_fmt_string(self):
        """Test _fmt with string value."""
        assert _fmt("hello") == "hello"

    def test_mag_none(self):
        """Test _mag with None value."""
        assert _mag(None) is None

    def test_mag_positive_float(self):
        """Test _mag with positive float."""
        assert _mag(3.14) == 3.14

    def test_mag_negative_float(self):
        """Test _mag with negative float."""
        assert _mag(-3.14) == 3.14

    def test_mag_positive_int(self):
        """Test _mag with positive int."""
        assert _mag(42) == 42

    def test_mag_negative_int(self):
        """Test _mag with negative int."""
        assert _mag(-42) == 42

    def test_mag_numeric_string(self):
        """Test _mag with numeric string."""
        assert _mag("-5.5") == 5.5

    def test_mag_non_numeric_string(self):
        """Test _mag with non-numeric string."""
        assert _mag("hello") is None

    def test_has_key_true(self):
        """Test _has_key when key exists."""
        logs = [
            {"readings": {"gs_voltage": 120.0, "gs_current": 5.0}},
            {"readings": {"ps_voltage": 48.0}}
        ]
        assert _has_key(logs, "gs_") is True

    def test_has_key_false(self):
        """Test _has_key when key doesn't exist."""
        logs = [
            {"readings": {"ps_voltage": 48.0, "ps_current": 10.0}},
        ]
        assert _has_key(logs, "gs_") is False

    def test_has_key_empty_logs(self):
        """Test _has_key with empty logs."""
        assert _has_key([], "gs_") is False

    def test_has_key_none_readings(self):
        """Test _has_key with None readings."""
        logs = [{"readings": None}]
        assert _has_key(logs, "gs_") is False

    def test_has_measure_true(self):
        """Test _has_measure when flag exists."""
        logs = [
            {"measure": {"gs": True, "ps": False}},
        ]
        assert _has_measure(logs, "gs") is True

    def test_has_measure_false(self):
        """Test _has_measure when flag doesn't exist."""
        logs = [
            {"measure": {"ps": True}},
        ]
        assert _has_measure(logs, "gs") is False

    def test_has_measure_empty_logs(self):
        """Test _has_measure with empty logs."""
        assert _has_measure([], "gs") is False

    def test_has_measure_none_measure(self):
        """Test _has_measure with None measure."""
        logs = [{"measure": None}]
        assert _has_measure(logs, "gs") is False


@pytest.mark.unit
class TestBuildRampSections:
    """Tests for _build_ramp_sections function."""

    def test_empty_steps(self):
        """Test with empty steps list."""
        result = _build_ramp_sections([])
        assert result == []

    def test_steps_without_ramp_logs(self):
        """Test with steps without ramp_logs."""
        steps = [{"action": "delay", "params": {}}]
        result = _build_ramp_sections(steps)
        assert result == []

    def test_steps_with_ramp_logs(self):
        """Test with steps containing ramp_logs."""
        steps = [{
            "index": 1,
            "action": "ramp_test",
            "ramp_logs": [
                {
                    "value": 100,
                    "status": "OK",
                    "message": "Step complete",
                    "readings": {
                        "gs_voltage": 120.0,
                        "gs_current": 5.0,
                        "gs_power": 600.0
                    }
                }
            ]
        }]
        result = _build_ramp_sections(steps)

        assert len(result) == 1
        assert "Step 1" in result[0]
        assert "ramp_test" in result[0]
        assert "120.000" in result[0]

    def test_efficiency_calculation(self):
        """Test efficiency is calculated correctly."""
        steps = [{
            "index": 1,
            "action": "ramp",
            "ramp_logs": [
                {
                    "value": 100,
                    "status": "OK",
                    "message": "",
                    "readings": {
                        "gs_voltage": 120.0,
                        "gs_power": 1000.0,
                        "ps_power": 900.0,
                    },
                    "measure": {"gs": True, "ps": True}
                }
            ]
        }]
        result = _build_ramp_sections(steps)

        assert len(result) == 1
        # Efficiency should be 90%
        assert "90.000" in result[0]


@pytest.mark.unit
class TestBuildShortCycleSections:
    """Tests for _build_short_cycle_sections function."""

    def test_empty_steps(self):
        """Test with empty steps list."""
        result = _build_short_cycle_sections([])
        assert result == []

    def test_steps_without_short_cycle_logs(self):
        """Test with steps without short_cycle_logs."""
        steps = [{"action": "delay", "params": {}}]
        result = _build_short_cycle_sections(steps)
        assert result == []

    def test_steps_with_short_cycle_logs(self):
        """Test with steps containing short_cycle_logs."""
        steps = [{
            "index": 1,
            "action": "short_cycle_test",
            "short_cycle_logs": [
                {
                    "cycle": 1,
                    "status": "OK",
                    "message": "Cycle complete",
                    "timestamp": "2024-01-01 12:00:00",
                    "timing": {
                        "pulse_set_s": 0.1,
                        "pulse_actual_s": 0.102,
                        "cycle_total_s": 1.5
                    },
                    "readings": {
                        "ps_voltage": 48.0,
                        "ps_current": 10.0,
                        "ps_power": 480.0,
                        "load_voltage": 48.0,
                        "load_current": 10.0,
                        "load_power": 480.0
                    },
                    "errors": []
                }
            ]
        }]
        result = _build_short_cycle_sections(steps)

        assert len(result) == 1
        assert "Step 1" in result[0]
        assert "Cycle" in result[0]


@pytest.mark.unit
class TestBuildLineLoadSections:
    """Tests for _build_line_load_sections function."""

    def test_empty_steps(self):
        """Test with empty steps list."""
        sections, plot_data = _build_line_load_sections([])
        assert sections == []
        assert plot_data == []

    def test_steps_without_line_load_logs(self):
        """Test with steps without line_load_logs."""
        steps = [{"action": "delay", "params": {}}]
        sections, plot_data = _build_line_load_sections(steps)
        assert sections == []
        assert plot_data == []

    def test_steps_with_line_load_logs(self):
        """Test with steps containing line_load_logs."""
        steps = [{
            "index": 1,
            "action": "line_load_test",
            "params": {},
            "line_load_logs": [
                {
                    "gs_set": 120.0,
                    "ps_set": 48.0,
                    "dl_set": 5.0,
                    "status": "OK",
                    "message": "",
                    "timestamp": "2024-01-01 12:00:00",
                    "readings": {
                        "gs_voltage": 120.0,
                        "gs_current": 5.0,
                        "gs_power": 600.0,
                        "ps_voltage": 48.0,
                        "ps_current": 10.0,
                        "ps_power": 480.0
                    }
                }
            ]
        }]
        sections, plot_data = _build_line_load_sections(steps)

        assert len(sections) == 1
        assert "Step 1" in sections[0]

    def test_plot_enabled(self):
        """Test with plot_efficiency enabled."""
        steps = [{
            "index": 1,
            "action": "line_load_test",
            "params": {"plot_efficiency": True},
            "line_load_logs": [
                {
                    "gs_set": 120.0,
                    "ps_set": 48.0,
                    "dl_set": 5.0,
                    "status": "OK",
                    "message": "",
                    "timestamp": "2024-01-01 12:00:00",
                    "readings": {
                        "gs_voltage": 120.0,
                        "gs_current": 5.0,
                        "gs_power": 600.0,
                        "ps_voltage": 48.0,
                        "ps_current": 10.0,
                        "ps_power": 480.0
                    }
                }
            ]
        }]
        sections, plot_data = _build_line_load_sections(steps)

        assert len(sections) == 1
        assert len(plot_data) == 1
        assert "line-load-plot-1" in plot_data[0]["id"]


@pytest.mark.unit
class TestGetPlotScript:
    """Tests for _get_plot_script function."""

    def test_empty_data(self):
        """Test with empty plot data."""
        result = _get_plot_script([])
        assert result == ""

    def test_no_points(self):
        """Test with data but no points."""
        result = _get_plot_script([{"id": "test", "points": []}])
        assert result == ""

    def test_with_data(self):
        """Test with valid plot data."""
        plot_data = [{
            "id": "test-plot",
            "points": [
                {"gs": 120.0, "ps": 48.0, "dl": 5.0, "eff": 90.0},
                {"gs": 130.0, "ps": 48.0, "dl": 5.0, "eff": 92.0}
            ]
        }]
        result = _get_plot_script(plot_data)

        assert "<script>" in result
        assert "lineLoadPlotData" in result
        assert "renderScatter" in result


@pytest.mark.unit
class TestGetReportCss:
    """Tests for _get_report_css function."""

    def test_returns_css(self):
        """Test that CSS is returned."""
        result = _get_report_css()

        assert "body" in result
        assert "font-family" in result
        assert ".container" in result
        assert ".status-pass" in result
        assert ".status-fail" in result


@pytest.mark.unit
class TestGenerateSequenceReport:
    """Tests for generate_sequence_report function."""

    def test_empty_report_data(self, tmp_path):
        """Test with empty report data."""
        result = generate_sequence_report(None)
        assert result is None

        result = generate_sequence_report({})
        assert result is None

    def test_minimal_report(self, tmp_path, monkeypatch):
        """Test with minimal report data."""
        monkeypatch.chdir(tmp_path)

        report_data = {
            "name": "Test Sequence",
            "start_time": datetime.now(),
            "steps": []
        }

        result = generate_sequence_report(report_data)

        assert result is not None
        assert result.exists()
        assert result.suffix == ".html"

        content = result.read_text()
        assert "Test Sequence" in content
        assert "PASS" in content

    def test_report_with_steps(self, tmp_path, monkeypatch):
        """Test report with steps."""
        monkeypatch.chdir(tmp_path)

        report_data = {
            "name": "Test Sequence",
            "start_time": datetime.now(),
            "steps": [
                {
                    "index": 1,
                    "action": "delay",
                    "params": "duration=1",
                    "status": "Pass",
                    "messages": ["Step completed"]
                },
                {
                    "index": 2,
                    "action": "ps_set_voltage",
                    "params": "voltage=12",
                    "status": "Pass",
                    "messages": ["Voltage set"]
                }
            ]
        }

        result = generate_sequence_report(report_data)

        assert result is not None
        content = result.read_text()
        assert "delay" in content
        assert "ps_set_voltage" in content
        assert "PASS" in content

    def test_report_with_failure(self, tmp_path, monkeypatch):
        """Test report with failed step."""
        monkeypatch.chdir(tmp_path)

        report_data = {
            "name": "Test Sequence",
            "start_time": datetime.now(),
            "steps": [
                {
                    "index": 1,
                    "action": "ps_set_voltage",
                    "params": "voltage=12",
                    "status": "Fail",
                    "messages": ["Connection failed"]
                }
            ]
        }

        result = generate_sequence_report(report_data)

        assert result is not None
        content = result.read_text()
        assert "FAIL" in content

    def test_output_callback(self, tmp_path, monkeypatch):
        """Test output callback is called."""
        monkeypatch.chdir(tmp_path)

        report_data = {
            "name": "Test Sequence",
            "start_time": datetime.now(),
            "steps": []
        }

        callback_messages = []

        def callback(msg):
            callback_messages.append(msg)

        result = generate_sequence_report(report_data, output_callback=callback)

        assert len(callback_messages) == 1
        assert "Report saved" in callback_messages[0]

    def test_logger_is_called(self, tmp_path, monkeypatch):
        """Test logger is called."""
        monkeypatch.chdir(tmp_path)

        report_data = {
            "name": "Test Sequence",
            "start_time": datetime.now(),
            "steps": []
        }

        mock_logger = Mock()
        result = generate_sequence_report(report_data, logger=mock_logger)

        mock_logger.info.assert_called_once()
        assert "report saved" in mock_logger.info.call_args[0][0].lower()

    def test_json_file_created(self, tmp_path, monkeypatch):
        """Test JSON file is also created."""
        monkeypatch.chdir(tmp_path)

        report_data = {
            "name": "Test Sequence",
            "start_time": datetime.now(),
            "steps": [
                {"index": 1, "action": "test", "status": "Pass", "messages": []}
            ]
        }

        result = generate_sequence_report(report_data)

        # JSON file should exist in same directory
        json_files = list(Path(tmp_path / "Test Results").glob("*.json"))
        assert len(json_files) == 1

    def test_report_with_metadata(self, tmp_path, monkeypatch):
        """Test report with metadata."""
        monkeypatch.chdir(tmp_path)

        report_data = {
            "name": "Test Sequence",
            "start_time": datetime.now(),
            "steps": [],
            "meta": {
                "operator": "TestUser",
                "dut": "TestDevice",
                "firmware": "v1.0.0"
            }
        }

        result = generate_sequence_report(report_data)

        content = result.read_text()
        assert "TestUser" in content
        assert "TestDevice" in content

    def test_report_with_ramp_logs(self, tmp_path, monkeypatch):
        """Test report with ramp logs."""
        monkeypatch.chdir(tmp_path)

        report_data = {
            "name": "Ramp Test",
            "start_time": datetime.now(),
            "steps": [{
                "index": 1,
                "action": "ramp",
                "status": "Pass",
                "messages": [],
                "ramp_logs": [
                    {
                        "value": 100,
                        "status": "OK",
                        "message": "Complete",
                        "readings": {"gs_voltage": 120.0}
                    }
                ]
            }]
        }

        result = generate_sequence_report(report_data)

        content = result.read_text()
        assert "Ramp Set" in content

    def test_sanitized_filename(self, tmp_path, monkeypatch):
        """Test filename is sanitized."""
        monkeypatch.chdir(tmp_path)

        report_data = {
            "name": "Test Sequence With Spaces",
            "start_time": datetime.now(),
            "steps": []
        }

        result = generate_sequence_report(report_data)

        # Spaces should be replaced with underscores
        assert "_" in result.name

    def test_creates_test_results_directory(self, tmp_path, monkeypatch):
        """Test that Test Results directory is created."""
        monkeypatch.chdir(tmp_path)

        report_data = {
            "name": "Test Sequence",
            "start_time": datetime.now(),
            "steps": []
        }

        result = generate_sequence_report(report_data)

        assert (tmp_path / "Test Results").exists()
        assert result.parent.name == "Test Results"
