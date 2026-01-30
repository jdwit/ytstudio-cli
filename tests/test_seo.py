"""Tests for SEO analysis."""

from typer.testing import CliRunner

from tests.conftest import MOCK_VIDEO, MOCK_VIDEO_SHORT_TITLE
from ytcli.commands.seo import DESC_MIN, TITLE_MAX, TITLE_MIN, analyze_seo, score_color
from ytcli.main import app

runner = CliRunner()


class TestAnalyzeSeo:
    """Test SEO analysis logic."""

    def test_good_seo_score(self):
        """Test video with good SEO gets reasonable score."""
        result = analyze_seo(MOCK_VIDEO)

        # Mock video has decent but not perfect SEO
        assert result["total_score"] >= 60
        assert result["tags_score"] == 100  # has 5 tags

    def test_bad_seo_score(self):
        """Test video with poor SEO gets low score."""
        result = analyze_seo(MOCK_VIDEO_SHORT_TITLE)

        assert result["total_score"] < 50
        assert result["title_score"] < 100
        assert result["desc_score"] == 0  # empty description
        assert result["tags_score"] == 0  # no tags

        assert "too short" in result["title_issues"][0]
        assert "empty" in result["desc_issues"][0]
        assert "no tags" in result["tags_issues"][0]

    def test_title_too_long(self):
        """Test penalty for title that's too long."""
        video = {
            **MOCK_VIDEO,
            "snippet": {
                **MOCK_VIDEO["snippet"],
                "title": "A" * (TITLE_MAX + 10),
            },
        }

        result = analyze_seo(video)
        assert result["title_score"] < 100
        assert "too long" in result["title_issues"][0]

    def test_title_minimum_length(self):
        """Test title minimum length threshold."""
        # Exactly at minimum should pass
        video = {
            **MOCK_VIDEO,
            "snippet": {
                **MOCK_VIDEO["snippet"],
                "title": "A" * TITLE_MIN,
            },
        }

        result = analyze_seo(video)
        assert len(result["title_issues"]) == 0

    def test_description_minimum_length(self):
        """Test description minimum length threshold."""
        video = {
            **MOCK_VIDEO,
            "snippet": {
                **MOCK_VIDEO["snippet"],
                "description": "A" * DESC_MIN,
            },
        }

        result = analyze_seo(video)
        assert result["desc_score"] == 100

    def test_tags_minimum_count(self):
        """Test tags minimum count threshold."""
        video = {
            **MOCK_VIDEO,
            "snippet": {
                **MOCK_VIDEO["snippet"],
                "tags": ["a", "b", "c", "d", "e"],  # exactly TAGS_MIN
            },
        }

        result = analyze_seo(video)
        assert result["tags_score"] == 100


class TestScoreColor:
    """Test score color helper."""

    def test_green_for_high_score(self):
        assert score_color(80) == "green"
        assert score_color(100) == "green"

    def test_yellow_for_medium_score(self):
        assert score_color(50) == "yellow"
        assert score_color(79) == "yellow"

    def test_red_for_low_score(self):
        assert score_color(0) == "red"
        assert score_color(49) == "red"


class TestSeoCheckCommand:
    """Test yt seo check command."""

    def test_check_video_seo(self, mock_auth):
        """Test checking SEO for a video."""
        result = runner.invoke(app, ["seo", "check", "test_video_123"])

        assert result.exit_code == 0
        assert "SEO Score" in result.stdout
        assert "Title" in result.stdout

    def test_check_video_seo_json(self, mock_auth):
        """Test checking SEO in JSON format."""
        result = runner.invoke(app, ["seo", "check", "test_video_123", "-o", "json"])

        assert result.exit_code == 0
        assert "total_score" in result.stdout
        assert "title_score" in result.stdout

    def test_check_video_not_found(self, mock_auth):
        """Test error when video not found."""
        mock_auth.videos.return_value.list.return_value.execute.return_value = {"items": []}

        result = runner.invoke(app, ["seo", "check", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout


class TestSeoAuditCommand:
    """Test yt seo audit command."""

    def test_audit_channel(self, mock_auth):
        """Test auditing channel SEO."""
        result = runner.invoke(app, ["seo", "audit"])

        assert result.exit_code == 0
        assert "SEO" in result.stdout

    def test_audit_channel_json(self, mock_auth):
        """Test auditing in JSON format."""
        result = runner.invoke(app, ["seo", "audit", "-o", "json"])

        assert result.exit_code == 0
        assert "average_score" in result.stdout
