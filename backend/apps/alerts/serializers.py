from rest_framework import serializers

from .models import Alert, AlertStatus, Severity, normalize_choice


class AlertSerializer(serializers.ModelSerializer):
    case_id_ref = serializers.SerializerMethodField()
    # Explicit CharFields: DRF ChoiceField would reject case-insensitive input
    # before validate_* could normalize it.
    severity = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Alert
        fields = [
            "id", "alert_id", "title", "desc", "severity", "status", "source",
            "source_uid", "rule_id", "rule_name", "correlation_uid", "tactic",
            "technique", "labels", "iocs", "first_seen", "last_seen", "case",
            "case_id_ref", "raw_data", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "alert_id", "created_at", "updated_at"]

    def get_case_id_ref(self, obj) -> dict | None:
        if obj.case_id is None:
            return None
        return {"id": obj.case_id, "case_id": obj.case.case_id, "title": obj.case.title}

    def validate_severity(self, value):
        return normalize_choice(Severity, value, Severity.UNKNOWN)

    def validate_status(self, value):
        return normalize_choice(AlertStatus, value, AlertStatus.NEW)
