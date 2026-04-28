from rest_framework import serializers
from .models import Worker, Tenant
from django.contrib.auth import get_user_model

User = get_user_model()


class WorkerSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    name = serializers.CharField(source="user.get_full_name", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Worker
        fields = ["id", "name", "email", "role", "tenant_name", "pages", "fields", "permissions"]

    def get_permissions(self, obj):
        return {
            "pages": obj.pages,
            "fields": obj.fields
        }


class WorkerCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, required=True)
    tenant = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Worker
        fields = ["email", "password", "role", "tenant"]

    def create(self, validated_data):
        email = validated_data.pop("email")
        password = validated_data.pop("password")
        tenant_id = validated_data.pop("tenant", None)

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})

        user = User.objects.create_user(
            email=email,
            password=password,
            role=validated_data.get("role", "worker")
        )

        tenant = None
        if tenant_id:
            from tenants.models import Tenant
            tenant = Tenant.objects.filter(id=tenant_id).first()

        worker = Worker.objects.create(user=user, tenant=tenant, **validated_data)
        return worker


class TenantSerializer(serializers.ModelSerializer):
    admin_email = serializers.EmailField(source="admin.email", read_only=True)
    worker_count = serializers.SerializerMethodField()
    path_slug = serializers.CharField(source="path_slug", read_only=True)

    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "admin_email",
            "worker_count",
            "created_at",
            "path_slug",
        ]

    def get_worker_count(self, obj):
        return obj.workers.count()


class TenantCreateSerializer(serializers.ModelSerializer):
    adminEmail = serializers.EmailField(write_only=True)

    class Meta:
        model = Tenant
        fields = ["name", "adminEmail"]
