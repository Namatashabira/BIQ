from rest_framework import serializers
from .models import Worker, Tenant
from django.contrib.auth import get_user_model

User = get_user_model()


class WorkerSerializer(serializers.ModelSerializer):
    email       = serializers.EmailField(source='user.email', read_only=True)
    name        = serializers.SerializerMethodField()
    username    = serializers.CharField(source='user.username', read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    school_role_display = serializers.CharField(source='get_school_role_display', read_only=True)
    avatar_url  = serializers.SerializerMethodField()

    class Meta:
        model  = Worker
        fields = ['id', 'name', 'username', 'email', 'school_role', 'school_role_display',
                  'tenant_name', 'pages', 'fields', 'avatar_url']

    def get_name(self, obj):
        if obj.user:
            full = obj.user.get_full_name()
            return full if full.strip() else obj.user.username
        return '—'

    def get_avatar_url(self, obj):
        if not obj.user:
            return None
        try:
            profile = obj.user.profile
            if profile.profile_picture:
                url = profile.profile_picture.url
                return url if url.startswith('http') else None
        except Exception:
            pass
        return None


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
