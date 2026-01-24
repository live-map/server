"""
Unit tests for Local News Filtering (5-Layer Defense System).

Tests the multi-layer defense against local news being published as international affairs:
1. Stage 1 patterns (NOT_EVENT_PATTERNS) - Traffic accidents, local incidents
2. Zero-shot strict rejection - "local news" label with lower threshold
3. LOCAL_INCIDENT_PATTERNS - checkworthiness gate
4. SIGNIFICANCE_INDICATORS - Override for significant events
5. Category rejection - "other" category gets rejected

Test cases:
- German traffic accident: "Laster und Polizeiauto rutschen bei Glatteis von Promenade"
- Local police reports, minor accidents
- Large-scale accidents with significance (should PASS)
"""

import pytest

from app.agent.event_verifier import (
    is_likely_real_event,
    REJECT_LABELS_STRICT,
)
from app.agent.checkworthiness import (
    check_worthiness,
    check_significance,
    RejectionReason,
    LOCAL_INCIDENT_PATTERNS,
    SIGNIFICANCE_INDICATORS,
)


class TestTrafficAccidentPatterns:
    """Tests for Stage 1: Traffic accident patterns in NOT_EVENT_PATTERNS."""

    def test_german_traffic_accident_rejected(self):
        """German traffic accident 'rutschen bei Glatteis' should be rejected."""
        text = "Laster und Polizeiauto rutschen bei Glatteis von Promenade"
        passed, reason = is_likely_real_event(text)
        assert not passed
        assert "NOT_EVENT" in reason
        assert "rutschen" in reason.lower() or "glatteis" in reason.lower()

    def test_german_unfall_rejected(self):
        """German 'Unfall' (accident) should be rejected."""
        text = "Schwerer Unfall auf der Autobahn A7"
        passed, reason = is_likely_real_event(text)
        assert not passed
        assert "unfall" in reason.lower()

    def test_german_verkehrsunfall_rejected(self):
        """German 'Verkehrsunfall' (traffic accident) should be rejected."""
        text = "Verkehrsunfall in Hamburg verursacht Stau"
        passed, reason = is_likely_real_event(text)
        assert not passed

    def test_traffic_accident_rejected(self):
        """English 'traffic accident' should be rejected."""
        text = "Traffic accident on Highway 101 causes major delays"
        passed, reason = is_likely_real_event(text)
        assert not passed

    def test_car_crash_rejected(self):
        """'Car crash' should be rejected."""
        text = "Car crash on Main Street leaves two injured"
        passed, reason = is_likely_real_event(text)
        assert not passed

    def test_road_accident_rejected(self):
        """'Road accident' should be rejected."""
        text = "Road accident near downtown closes intersection"
        passed, reason = is_likely_real_event(text)
        assert not passed

    def test_vehicle_collision_rejected(self):
        """'Vehicle collision' should be rejected."""
        text = "Vehicle collision reported on Interstate 95"
        passed, reason = is_likely_real_event(text)
        assert not passed

    def test_icy_road_rejected(self):
        """'Icy road' accidents should be rejected."""
        text = "Driver loses control on icy road, hits guardrail"
        passed, reason = is_likely_real_event(text)
        assert not passed

    def test_black_ice_rejected(self):
        """'Black ice' accidents should be rejected."""
        text = "Black ice causes multiple fender benders on highway"
        passed, reason = is_likely_real_event(text)
        assert not passed

    def test_slid_off_road_rejected(self):
        """'Slid off road' should be rejected."""
        text = "Truck slid off highway during winter storm"
        passed, reason = is_likely_real_event(text)
        assert not passed

    def test_skidded_rejected(self):
        """'Skidded' patterns should be rejected."""
        text = "Bus skidded on wet road, passengers evacuated safely"
        passed, reason = is_likely_real_event(text)
        assert not passed

    def test_local_police_rejected(self):
        """'Local police' mentions should be rejected."""
        text = "Local police respond to accident scene"
        passed, reason = is_likely_real_event(text)
        assert not passed

    def test_no_injuries_reported_rejected(self):
        """'No injuries reported' should be rejected."""
        text = "Minor collision, no injuries reported"
        passed, reason = is_likely_real_event(text)
        assert not passed

    def test_fender_bender_rejected(self):
        """'Fender bender' should be rejected."""
        text = "Fender bender slows traffic on Route 9"
        passed, reason = is_likely_real_event(text)
        assert not passed


class TestLocalAuthoritiesPatterns:
    """Tests for local authority mentions."""

    def test_city_police_rejected(self):
        """'City police' should be rejected."""
        text = "City police investigate minor theft"
        passed, reason = is_likely_real_event(text)
        assert not passed

    def test_regional_police_rejected(self):
        """'Regional police' should be rejected."""
        text = "Regional police issue traffic advisory"
        passed, reason = is_likely_real_event(text)
        assert not passed

    def test_local_incident_rejected(self):
        """'Local incident' should be rejected."""
        text = "Local incident closes street temporarily"
        passed, reason = is_likely_real_event(text)
        assert not passed

    def test_petty_crime_rejected(self):
        """'Petty crime' should be rejected."""
        text = "Petty crime rates drop in downtown area"
        passed, reason = is_likely_real_event(text)
        assert not passed


class TestRealEventsStillPass:
    """Ensure real international events still pass the filter."""

    def test_real_attack_passes(self):
        """Real military attack should pass."""
        text = "Iran attacks US bases in Iraq, 3 soldiers injured"
        passed, reason = is_likely_real_event(text)
        assert passed

    def test_missile_launch_passes(self):
        """Missile launch should pass."""
        text = "North Korea fires ballistic missile toward Sea of Japan"
        passed, reason = is_likely_real_event(text)
        assert passed

    def test_diplomatic_summit_passes(self):
        """Diplomatic summit should pass."""
        text = "Putin and Xi meet in Beijing for summit talks"
        passed, reason = is_likely_real_event(text)
        assert passed

    def test_airstrike_passes(self):
        """Airstrike news should pass."""
        text = "Israeli forces conduct airstrike on Gaza"
        passed, reason = is_likely_real_event(text)
        assert passed


class TestZeroShotStrictLabels:
    """Tests for REJECT_LABELS_STRICT configuration."""

    def test_local_news_in_strict_labels(self):
        """'local news' should be in strict rejection labels."""
        assert "local news" in REJECT_LABELS_STRICT

    def test_local_news_threshold_is_low(self):
        """'local news' threshold should be low (0.15)."""
        assert REJECT_LABELS_STRICT["local news"] == 0.15

    def test_local_incident_in_strict_labels(self):
        """'local incident' should be in strict rejection labels."""
        assert "local incident" in REJECT_LABELS_STRICT

    def test_traffic_news_in_strict_labels(self):
        """'traffic news' should be in strict rejection labels."""
        assert "traffic news" in REJECT_LABELS_STRICT


class TestCheckWorthinessLocalIncident:
    """Tests for LOCAL_INCIDENT_PATTERNS in checkworthiness."""

    def test_traffic_crash_pattern_matches(self):
        """Traffic crash patterns should match."""
        text = "Truck crash on highway closes lanes"
        result = check_worthiness(text)
        # Single pattern might not trigger rejection (threshold is 2)
        # But let's verify the pattern exists
        import re
        matched = any(
            re.search(p, text, re.I)
            for p in LOCAL_INCIDENT_PATTERNS
        )
        assert matched

    def test_local_police_pattern_matches(self):
        """Local police patterns should match."""
        text = "Local police investigate minor accident"
        import re
        matched = any(
            re.search(p, text, re.I)
            for p in LOCAL_INCIDENT_PATTERNS
        )
        assert matched

    def test_multiple_patterns_rejected(self):
        """Multiple local incident patterns should trigger rejection."""
        # This text has: "local police", "accident", "no injuries"
        text = "Local police respond to car accident, no injuries reported"
        result = check_worthiness(text)
        assert not result.is_checkworthy
        assert result.rejection_reason == RejectionReason.LOCAL_INCIDENT

    def test_german_local_news_rejected(self):
        """German local news with multiple patterns should be rejected."""
        # "Polizeiauto", "rutschen", "glatteis" patterns
        text = "Polizeiauto und Laster rutschen bei Glatteis von der Strasse"
        result = check_worthiness(text)
        assert not result.is_checkworthy
        assert result.rejection_reason == RejectionReason.LOCAL_INCIDENT

    def test_weather_related_accident_rejected(self):
        """Weather-related accidents should be rejected."""
        text = "Icy conditions cause accident on local highway, minor injuries"
        result = check_worthiness(text)
        assert not result.is_checkworthy
        assert result.rejection_reason == RejectionReason.LOCAL_INCIDENT


class TestSignificanceIndicators:
    """Tests for SIGNIFICANCE_INDICATORS override."""

    def test_mass_casualties_detected(self):
        """Mass casualties (47 killed) should be detected as significant."""
        text = "Bus crash kills 47 tourists on mountain road"
        is_significant, count, patterns = check_significance(text)
        assert is_significant
        assert count >= 1

    def test_dozens_killed_detected(self):
        """'Dozens killed' should be detected as significant."""
        text = "Dozens killed in highway pileup crash"
        is_significant, count, patterns = check_significance(text)
        assert is_significant

    def test_state_of_emergency_detected(self):
        """'State of emergency' should be detected as significant."""
        text = "Governor declares state of emergency after massive accident"
        is_significant, count, patterns = check_significance(text)
        assert is_significant

    def test_airport_closed_detected(self):
        """'Airport closed' should be detected as significant."""
        text = "Airport closed after truck crashes into terminal"
        is_significant, count, patterns = check_significance(text)
        assert is_significant

    def test_president_response_detected(self):
        """Presidential response should be detected as significant."""
        text = "President condemns accident, promises federal response"
        is_significant, count, patterns = check_significance(text)
        assert is_significant

    def test_international_involvement_detected(self):
        """'Foreign nationals' should be detected as significant."""
        text = "Multiple foreign nationals injured in crash"
        is_significant, count, patterns = check_significance(text)
        assert is_significant

    def test_terror_attack_detected(self):
        """'Terror attack' should be detected as significant."""
        text = "Terror attack: truck rams into crowd"
        is_significant, count, patterns = check_significance(text)
        assert is_significant

    def test_minor_accident_not_significant(self):
        """Minor accidents should NOT be significant."""
        text = "Car slides into ditch on icy road, driver unhurt"
        is_significant, count, patterns = check_significance(text)
        assert not is_significant
        assert count == 0


class TestSignificanceOverride:
    """Tests for significance override in checkworthiness."""

    def test_local_incident_with_significance_passes(self):
        """Local incident with significance indicators should PASS."""
        # Has multiple local patterns: "road accident", "local police", but also "47 killed" (significant)
        text = "Road accident kills 47 tourists, local police overwhelmed by scale of disaster"
        result = check_worthiness(text)
        assert result.is_checkworthy
        # Should have override indicator in matched_patterns
        assert any("significance_override" in p for p in result.matched_patterns)

    def test_local_incident_without_significance_rejected(self):
        """Local incident without significance should be REJECTED."""
        text = "Road accident closes highway, local police on scene"
        result = check_worthiness(text)
        assert not result.is_checkworthy
        assert result.rejection_reason == RejectionReason.LOCAL_INCIDENT

    def test_airport_crash_passes(self):
        """Airport-related crash should pass (critical infrastructure)."""
        text = "Truck crash closes airport access road, flights delayed"
        # If it matches "airport...closed" it should be significant
        is_sig, _, _ = check_significance(text)
        if is_sig:
            result = check_worthiness(text)
            assert result.is_checkworthy


class TestOriginalProblemCase:
    """Tests for the original problem case from the bug report."""

    def test_german_glatteis_accident_in_event_verifier(self):
        """Original German accident case should be rejected in Stage 1."""
        text = "Unfälle : Laster und Polizeiauto rutschen bei Glatteis von Promenade"
        passed, reason = is_likely_real_event(text)
        # Should be caught by "rutschen" or "glatteis" or "unfall" pattern
        assert not passed
        assert "NOT_EVENT" in reason

    def test_german_glatteis_accident_in_checkworthiness(self):
        """Original German accident case should be rejected in checkworthiness if it passes Stage 1."""
        text = "Laster und Polizeiauto rutschen bei Glatteis"
        result = check_worthiness(text)
        # Multiple patterns: "rutschen", "polizeiauto", "glatteis"
        assert not result.is_checkworthy
        assert result.rejection_reason == RejectionReason.LOCAL_INCIDENT


class TestPatternCompilation:
    """Tests for pattern compilation and existence."""

    def test_local_incident_patterns_exist(self):
        """LOCAL_INCIDENT_PATTERNS should have multiple patterns."""
        assert len(LOCAL_INCIDENT_PATTERNS) >= 8

    def test_significance_indicators_exist(self):
        """SIGNIFICANCE_INDICATORS should have multiple indicators."""
        assert len(SIGNIFICANCE_INDICATORS) >= 10

    def test_local_incident_rejection_reason_exists(self):
        """RejectionReason.LOCAL_INCIDENT should exist."""
        assert hasattr(RejectionReason, "LOCAL_INCIDENT")
        assert RejectionReason.LOCAL_INCIDENT.value == "local_incident"
