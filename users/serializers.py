from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import UserProfile

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class UserProfileSerializer(serializers.ModelSerializer):
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ['id', 'name', 'email', 'phone', 'address', 'profile_picture', 'profile_picture_url', 'guest_token', 'user', 'created_at', 'updated_at']
        read_only_fields = ['id', 'profile_picture_url', 'created_at', 'updated_at']

    def get_profile_picture_url(self, obj):
        if obj.profile_picture:
            try:
                url = obj.profile_picture.url
                if url.startswith('http://') or url.startswith('https://'):
                    return url
                request = self.context.get('request')
                return request.build_absolute_uri(url) if request else url
            except Exception:
                return None
        return None


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'password', 'username']

    def create(self, validated_data):
        # Ensure username is non-empty
        username = validated_data.get('username') or validated_data['email'].split('@')[0]
        user = User.objects.create_user(
            email=validated_data['email'],
            username=username,
            password=validated_data['password']
        )
        user.is_active = True  # Ensure new users are active by default
        user.save()
        # Attach tenant info if available
        from tenants.models import Tenant
        tenant = Tenant.objects.filter(admin=user).first()
        user.tenant = tenant if tenant else None
        return user


class UserWithProfileSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(required=False, context={'request': None})

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'profile']
        read_only_fields = ['id', 'date_joined']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pass request context down to nested profile serializer
        request = self.context.get('request')
        if request:
            self.fields['profile'].context['request'] = request

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', None)

        # Update User fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update or create related profile
        if profile_data:
            profile, _ = UserProfile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance
