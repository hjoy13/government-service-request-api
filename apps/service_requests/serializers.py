from rest_framework import serializers

from .models import ServiceRequest

RESTRICTED_CREATE_FIELDS = {"status", "assigned_to", "created_by"}


class ServiceRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceRequest
        fields = (
            "id", "category", "title", "description", "priority", "status",
            "created_by", "assigned_to", "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "status", "created_by", "assigned_to", "created_at", "updated_at",
        )

    def validate_category(self, value):
        if not value.is_active:
            raise serializers.ValidationError("This category is not accepting new requests.")
        return value

    def validate(self, attrs):
        if self.instance is None:
            restricted = RESTRICTED_CREATE_FIELDS.intersection(self.initial_data)
            if restricted:
                raise serializers.ValidationError(
                    {field: "This field is set by the system and cannot be provided."
                     for field in sorted(restricted)}
                )
        return attrs