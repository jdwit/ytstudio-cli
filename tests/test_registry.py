from ytstudio.registry import (
    DIMENSION_GROUPS,
    DIMENSIONS,
    METRIC_GROUPS,
    METRICS,
    find_closest_dimension,
    find_closest_metric,
    validate_dimensions,
    validate_metrics,
)


class TestMetricsRegistry:
    def test_has_core_metrics(self):
        core = [m for m in METRICS.values() if m.core]
        assert len(core) >= 10

    def test_views_is_core(self):
        assert "views" in METRICS
        assert METRICS["views"].core is True

    def test_revenue_metrics_are_monetary(self):
        revenue = [m for m in METRICS.values() if m.group == "revenue"]
        assert all(m.monetary for m in revenue)

    def test_groups_are_consistent(self):
        for m in METRICS.values():
            assert m.group in METRIC_GROUPS

    def test_no_duplicate_names(self):
        names = [m.name for m in METRICS.values()]
        assert len(names) == len(set(names))


class TestDimensionsRegistry:
    def test_has_common_dimensions(self):
        for name in ["day", "month", "country", "video", "deviceType"]:
            assert name in DIMENSIONS

    def test_filter_only_dimensions(self):
        assert DIMENSIONS["continent"].filter_only is True
        assert DIMENSIONS["day"].filter_only is False

    def test_groups_are_consistent(self):
        for d in DIMENSIONS.values():
            assert d.group in DIMENSION_GROUPS

    def test_no_duplicate_names(self):
        names = [d.name for d in DIMENSIONS.values()]
        assert len(names) == len(set(names))


class TestValidation:
    def test_valid_metrics(self):
        errors = validate_metrics(["views", "likes", "comments"])
        assert errors == []

    def test_invalid_metric(self):
        errors = validate_metrics(["views", "veiws"])
        assert len(errors) == 1
        assert "veiws" in errors[0]

    def test_valid_dimensions(self):
        errors = validate_dimensions(["day", "country"])
        assert errors == []

    def test_invalid_dimension(self):
        errors = validate_dimensions(["cuntry"])
        assert len(errors) == 1
        assert "cuntry" in errors[0]


class TestFuzzyMatching:
    def test_close_metric(self):
        assert find_closest_metric("veiws") == "views"
        assert find_closest_metric("liks") == "likes"
        assert find_closest_metric("commets") == "comments"

    def test_no_match(self):
        assert find_closest_metric("zzzzzzzzz") is None

    def test_close_dimension(self):
        assert find_closest_dimension("contry") == "country"
        assert find_closest_dimension("vidoe") == "video"

    def test_case_insensitive(self):
        assert find_closest_metric("Views") == "views"
        assert find_closest_metric("LIKES") == "likes"
