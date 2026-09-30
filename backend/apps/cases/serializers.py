from rest_framework import serializers

from apps.accounts.models import User
from apps.alerts.models import Severity, normalize_choice

from .models import Case, CaseEvent, CaseStatus, CaseVerdict


class CaseEventSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.username", default=None, read_only=True)

    class Meta:
        model = CaseEvent
        fields = ["id", "kind", "message", "data", "actor", "created_at"]


class CaseAlertLinkSerializer(serializers.Serializer):
    """Light alert reference nested in case detail."""
    id = serializers.IntegerField()
    alert_id = serializers.CharField()
    title = serializers.CharField()
    severity = serializers.CharField()
    status = serializers.CharField()


class CaseSerializer(serializers.ModelSerializer):
    alert_count = serializers.IntegerField(read_only=True)
    assignee = serializers.SlugRelatedField(
        slug_field="username", queryset=User.objects.all(), required=False, allow_null=True
    )
    # Explicit CharFields so validate_* can normalize case-insensitive input
    # (DRF ChoiceField would reject it first).
    severity = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(required=False, allow_blank=True)
    verdict = serializers.CharField(required=False, allow_blank=True)
    alerts = serializers.SerializerMethodField()
    events = serializers.SerializerMethodField()

    class Meta:
        model = Case
        fields = [
            "id", "case_id", "title", "description", "severity", "priority",
            "status", "verdict", "summary", "tags", "assignee", "correlation_uid",
            "closed_time", "severity_ai", "confidence_ai", "priority_ai",
            "verdict_ai", "investigation_report_ai_json", "alert_count",
            "alerts", "events", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "case_id", "created_at", "updated_at"]

    def get_alerts(self, obj) -> list:
        if not self.context.get("detail"):
            return []
        from apps.alerts.serializers import AlertSerializer
        return AlertSerializer(obj.alerts.all()[:200], many=True).data

    def get_events(self, obj) -> list:
        if not self.context.get("detail"):
            return []
        return CaseEventSerializer(obj.events.select_related("actor")[:100], many=True).data

    def validate_severity(self, value):
        return normalize_choice(Severity, value, "")

    def validate_priority(self, value):
        return normalize_choice(Severity, value, "")

    def validate_status(self, value):
        return normalize_choice(CaseStatus, value, CaseStatus.NEW)

    def validate_verdict(self, value):
        return normalize_choice(CaseVerdict, value, CaseVerdict.UNKNOWN)
