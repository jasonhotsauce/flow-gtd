"""Tests for tag extraction and normalization."""

import pytest
from unittest.mock import patch, MagicMock

from flow.core.tagging import (
    normalize_tag,
    parse_user_tags,
    suggest_tags_from_vocabulary,
    extract_tags,
)


class TestNormalizeTag:
    """Tests for tag normalization."""

    def test_lowercase(self):
        """Tags are converted to lowercase."""
        assert normalize_tag("CodeReview") == "codereview"
        assert normalize_tag("API") == "api"

    def test_spaces_to_hyphens(self):
        """Spaces are converted to hyphens."""
        assert normalize_tag("code review") == "code-review"
        assert normalize_tag("api  design") == "api-design"

    def test_underscores_to_hyphens(self):
        """Underscores are converted to hyphens."""
        assert normalize_tag("code_review") == "code-review"
        assert normalize_tag("api_design_doc") == "api-design-doc"

    def test_strips_whitespace(self):
        """Leading and trailing whitespace is stripped."""
        assert normalize_tag("  auth  ") == "auth"
        assert normalize_tag("\tbackend\n") == "backend"

    def test_removes_special_chars(self):
        """Special characters are removed."""
        assert normalize_tag("api@design!") == "apidesign"
        assert normalize_tag("code#review$") == "codereview"

    def test_collapse_multiple_hyphens(self):
        """Multiple hyphens are collapsed to one."""
        assert normalize_tag("code--review") == "code-review"
        assert normalize_tag("api---design") == "api-design"

    def test_empty_string(self):
        """Empty strings remain empty."""
        assert normalize_tag("") == ""
        assert normalize_tag("   ") == ""


class TestParseUserTags:
    """Tests for parsing user tag input."""

    def test_simple_tag_names(self):
        """Parse comma-separated tag names."""
        existing = ["auth", "backend", "frontend"]
        result = parse_user_tags("auth, backend", existing)
        assert result == ["auth", "backend"]

    def test_numeric_references(self):
        """Parse numeric references to existing tags."""
        existing = ["auth", "backend", "frontend"]
        result = parse_user_tags("1, 2", existing)
        assert result == ["auth", "backend"]

    def test_new_tag_syntax(self):
        """Parse NEW:tag-name syntax for creating new tags."""
        existing = ["auth", "backend"]
        result = parse_user_tags("NEW:my-new-tag, auth", existing)
        assert result == ["my-new-tag", "auth"]

    def test_mixed_input(self):
        """Parse mixed numeric, name, and NEW: inputs."""
        existing = ["auth", "backend", "frontend"]
        result = parse_user_tags("1, api, NEW:custom-tag", existing)
        assert result == ["auth", "api", "custom-tag"]

    def test_removes_duplicates(self):
        """Duplicate tags are removed."""
        existing = ["auth", "backend"]
        result = parse_user_tags("auth, auth, 1", existing)
        assert result == ["auth"]

    def test_empty_input(self):
        """Empty input returns empty list."""
        assert parse_user_tags("", []) == []
        assert parse_user_tags("   ", ["auth"]) == []

    def test_invalid_numeric_reference(self):
        """Invalid numeric references are ignored."""
        existing = ["auth", "backend"]
        result = parse_user_tags("99, auth", existing)
        assert result == ["auth"]

    def test_normalizes_new_tags(self):
        """New tags are normalized."""
        existing = []
        result = parse_user_tags("NEW:My New Tag", existing)
        assert result == ["my-new-tag"]


class TestSuggestTagsFromVocabulary:
    """Tests for keyword-based tag suggestions."""

    def test_exact_match(self):
        """Tags matching exactly are suggested."""
        existing = ["auth", "backend", "api"]
        result = suggest_tags_from_vocabulary("implement auth flow", existing)
        assert "auth" in result

    def test_partial_match(self):
        """Tags with matching parts are suggested."""
        existing = ["code-review", "api-design", "frontend"]
        result = suggest_tags_from_vocabulary("reviewing the code", existing)
        assert "code-review" in result

    def test_no_match(self):
        """No suggestions when nothing matches."""
        existing = ["auth", "backend", "api"]
        result = suggest_tags_from_vocabulary("buy groceries", existing)
        assert result == []

    def test_max_suggestions(self):
        """Limits number of suggestions."""
        existing = ["a", "b", "c", "d", "e"]
        result = suggest_tags_from_vocabulary("a b c d e", existing, max_suggestions=3)
        assert len(result) == 3


class TestExtractTags:
    """Tests for LLM-based tag extraction."""

    @patch("flow.core.tagging.complete_json")
    def test_extracts_tags_from_llm_response(self, mock_complete):
        """Tags are extracted from LLM JSON response."""
        mock_complete.return_value = {"tags": ["auth", "backend", "api"]}

        result = extract_tags("implement oauth login", "text")

        assert result == ["auth", "backend", "api"]
        mock_complete.assert_called_once()

    @patch("flow.core.tagging.complete_json")
    def test_normalizes_llm_tags(self, mock_complete):
        """Tags from LLM are normalized."""
        mock_complete.return_value = {"tags": ["Code Review", "API_Design"]}

        result = extract_tags("review the code", "text")

        assert result == ["code-review", "api-design"]

    @patch("flow.core.tagging.complete_json")
    def test_limits_to_5_tags(self, mock_complete):
        """Maximum of 5 tags are returned."""
        mock_complete.return_value = {"tags": ["a", "b", "c", "d", "e", "f", "g"]}

        result = extract_tags("content", "text")

        assert len(result) == 5

    @patch("flow.core.tagging.complete_json")
    def test_handles_llm_failure(self, mock_complete):
        """Returns empty list on LLM failure."""
        mock_complete.side_effect = RuntimeError("LLM unavailable")

        result = extract_tags("content", "text")

        assert result == []

    @patch("flow.core.tagging.complete_json")
    def test_handles_invalid_response(self, mock_complete):
        """Returns empty list when LLM returns invalid format."""
        mock_complete.return_value = {"invalid": "response"}

        result = extract_tags("content", "text")

        assert result == []

    @patch("flow.core.tagging.complete_json")
    def test_handles_none_response(self, mock_complete):
        """Returns empty list when LLM returns None."""
        mock_complete.return_value = None

        result = extract_tags("content", "text")

        assert result == []

    @patch("flow.core.tagging.complete_json")
    def test_truncates_long_content(self, mock_complete):
        """Long content is truncated before sending to LLM."""
        mock_complete.return_value = {"tags": ["test"]}
        long_content = "x" * 1000

        extract_tags(long_content, "text", max_content_length=100)

        # Check that the prompt received truncated content
        call_args = mock_complete.call_args[0][0]
        assert "xxx..." in call_args  # Truncation indicator

    @patch("flow.core.tagging.complete_json")
    def test_includes_existing_tags_in_prompt(self, mock_complete):
        """Existing tags are included in prompt for consistency."""
        mock_complete.return_value = {"tags": ["auth"]}
        existing = ["auth", "backend", "frontend"]

        extract_tags("content", "text", existing_tags=existing)

        call_args = mock_complete.call_args[0][0]
        assert "auth" in call_args
        assert "backend" in call_args
