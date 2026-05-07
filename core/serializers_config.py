# core/serializers_config.py
"""
Serializers for business configuration, feature toggles, and terminology.
"""
from rest_framework import serializers
from .business_config import (
    BusinessConfig,
    FeatureToggle,
    Terminology,
    Theme,
    PricingSettings,
    WorkerAccessInvite,
    WorkerPageAccess,
    BUSINESS_PRESETS,
)


class FeatureToggleSerializer(serializers.ModelSerializer):
    """Serializer for feature toggles"""
    feature_display = serializers.CharField(source='get_feature_key_display', read_only=True)
    
    class Meta:
        model = FeatureToggle
        fields = ['id', 'feature_key', 'feature_display', 'enabled', 'notes']
        read_only_fields = ['id']


class TerminologySerializer(serializers.ModelSerializer):
    """Serializer for terminology"""
    entity_display = serializers.CharField(source='get_entity_display', read_only=True)
    
    class Meta:
        model = Terminology
        fields = ['id', 'entity', 'entity_display', 'label', 'label_plural', 'description']
        read_only_fields = ['id']


class BusinessConfigSerializer(serializers.ModelSerializer):
    """Serializer for business configuration"""
    business_type_display = serializers.CharField(source='get_business_type_display', read_only=True)
    feature_toggles = FeatureToggleSerializer(many=True, source='tenant.feature_toggles', read_only=True)
    terminology = TerminologySerializer(many=True, source='tenant.terminology', read_only=True)
    
    class Meta:
        model = BusinessConfig
        fields = [
            'id', 
            'business_type', 
            'business_type_display',
            'industry_description',
            'onboarding_completed',
            'preset_applied',
            'feature_toggles',
            'terminology',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'preset_applied', 'created_at', 'updated_at']


class BusinessPresetSerializer(serializers.Serializer):
    """Serializer for available business presets"""
    type = serializers.CharField()
    display_name = serializers.CharField()
    description = serializers.CharField()
    features = serializers.DictField()
    terminology = serializers.DictField()


class ApplyPresetSerializer(serializers.Serializer):
    """Serializer for applying a business preset"""
    business_type = serializers.ChoiceField(choices=BusinessConfig.BUSINESS_TYPE_CHOICES)


class ConfigurationSummarySerializer(serializers.Serializer):
    """
    Summary serializer that returns all configuration for a tenant.
    This is used by the frontend to get all labels and features in one call.
    """
    business_type = serializers.CharField()
    features = serializers.DictField()
    labels = serializers.DictField()
    theme = serializers.DictField()
    onboarding_completed = serializers.BooleanField()


class ThemeSerializer(serializers.ModelSerializer):
    """Serializer for theme - stores color identifier and returns full triplet"""
    logo_url = serializers.SerializerMethodField()
    primary_color = serializers.SerializerMethodField()
    secondary_color = serializers.SerializerMethodField()
    accent_color = serializers.SerializerMethodField()
    
    class Meta:
        model = Theme
        fields = ['id', 'logo', 'logo_url', 'color', 'primary_color', 'secondary_color', 'accent_color']
        read_only_fields = ['id', 'logo_url', 'primary_color', 'secondary_color', 'accent_color']
    
    def get_logo_url(self, obj):
        if obj.logo:
            try:
                url = obj.logo.url
                # Cloudinary returns full https:// URLs — return as-is
                if url.startswith('http://') or url.startswith('https://'):
                    return url
                # Fallback for local dev
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(url)
                return url
            except Exception:
                return None
        return None
    
    def get_primary_color(self, obj):
        return obj.primary_color
    
    def get_secondary_color(self, obj):
        return obj.secondary_color
    
    def get_accent_color(self, obj):
        return obj.accent_color


class PricingSettingsSerializer(serializers.ModelSerializer):
    """Serializer for pricing and currency settings."""

    class Meta:
        model = PricingSettings
        fields = [
            'id',
            'default_currency',
            'country',
            'wholesale_threshold',
            'price_priority',
            'wholesale_availability',
            'enable_tax',
            'tax_mode',
            'price_missing',
            'rounding',
            'order_limit_min',
            'order_limit_max',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_wholesale_availability(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('wholesale_availability must be a list')
        return value


class WorkerAccessInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkerAccessInvite
        fields = [
            'id', 'name', 'email', 'username', 'school_role',
            'otp_code', 'otp_expires_at', 'used', 'allowed_pages', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'otp_code', 'otp_expires_at', 'used', 'created_at', 'updated_at']


class WorkerPageAccessSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = WorkerPageAccess
        fields = ['id', 'user', 'user_email', 'user_name', 'allowed_pages', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user_email', 'user_name', 'created_at', 'updated_at']
