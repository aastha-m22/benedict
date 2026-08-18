"""Tests for Slack message formatting helpers."""

from benedict.slack_app import parse_error_message


def test_parse_error_message_blank_line_body():
    error_type, body, next_steps = parse_error_message(
        "⚠️ Repository Read Error\n\nError reading repository `example`."
    )
    assert error_type == "Repository Read Error"
    assert "Error reading repository" in body
    assert next_steps is None


def test_parse_error_message_single_newline_does_not_double_wrap():
    error_type, body, next_steps = parse_error_message(
        "⚠️ Some operations failed:\n- Metadata file not found"
    )
    assert error_type == "Some operations failed"
    assert body == "- Metadata file not found"
    assert next_steps is None


def test_parse_error_message_plain_text_fallback():
    error_type, body, next_steps = parse_error_message("something went wrong")
    assert error_type == "Error"
    assert body == "something went wrong"
    assert next_steps is None
