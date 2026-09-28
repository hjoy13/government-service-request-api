from rest_framework import serializers

from .models import ServiceRequest, Comment
from django.contrib.auth import get_user_model

User = get_user_model()

RESTRICTED_CREATE_FIELDS = {"status", "assigned_to", "created_by"}

CITIZEN_EDITABLE_FIELDS = {"title", "description", "category", "attachment"}
STAFF_EDITABLE_FIELDS = {"status", "priority"}


def editable_fields_for(user):
    if getattr(user, "is_citizen", False):
        return CITIZEN_EDITABLE_FIELDS
    if getattr(user, "is_officer", False) or getattr(user, "is_admin_role", False):
        return STAFF_EDITABLE_FIELDS
    return set()


class ServiceRequestSerializer(serializers.ModelSerializer):
    has_attachment = serializers.SerializerMethodField()

    class Meta:
        model = ServiceRequest
        fields = (
            "id", "category", "title", "description", "priority", "status",
            "created_by", "assigned_to", "attachment", "has_attachment",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_by", "assigned_to", "created_at", "updated_at")
        extra_kwargs = {"attachment": {"write_only": True}}

    def get_has_attachment(self, obj) -> bool:
        return bool(obj.attachment)

    def validate_category(self, value):
        if not value.is_active:
            raise serializers.ValidationError("This category is not accepting new requests.")
        return value

    def validate(self, attrs):
        if self.instance is None:
            self._validate_create()
        else:
            self._validate_update()
        return attrs

    def _validate_create(self):
        restricted = RESTRICTED_CREATE_FIELDS.intersection(self.initial_data)
        if restricted:
            raise serializers.ValidationError(
                {field: "This field is set by the system and cannot be provided."
                 for field in sorted(restricted)}
            )

    def _validate_update(self):
        user = self.context["request"].user
        forbidden = set(self.initial_data) - editable_fields_for(user)
        if forbidden:
            raise serializers.ValidationError(
                {field: "You are not allowed to change this field."
                 for field in sorted(forbidden)}
            )

        if getattr(user, "is_citizen", False) and self.instance.status != ServiceRequest.Status.OPEN:
            raise serializers.ValidationError(
                "This request can only be edited while its status is OPEN."
            )

class AssignOfficerSerializer(serializers.Serializer):
    officer_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.Role.OFFICER, is_active=True),
        error_messages={
            "does_not_exist": "No active officer with id {pk_value}.",
            "incorrect_type": "officer_id must be an integer.",
        },
    )        

class CommentSerializer(serializers.ModelSerializer):
    WRITABLE_FIELDS = {"text"}

    text = serializers.CharField(max_length=2000)

    class Meta:
        model = Comment
        fields = ["id", "service_request", "author", "text", "created_at"]
        read_only_fields = ["id", "service_request", "author", "created_at"]

    def validate(self, attrs):
        unexpected = set(self.initial_data) - self.WRITABLE_FIELDS
        if unexpected:
            raise serializers.ValidationError(
                {field: "This field cannot be set." for field in sorted(unexpected)}
            )
        return attrs

class ServiceRequestCreateSerializer(serializers.ModelSerializer):
    """Documentation only: the fields a citizen may send when creating a request.

    The real create logic still runs through ServiceRequestSerializer; this class
    exists so the OpenAPI schema does not advertise server-owned fields (status,
    assigned_to, created_by) as create inputs.
    """

    class Meta:
        model = ServiceRequest
        fields = ("category", "title", "description", "priority", "attachment")    