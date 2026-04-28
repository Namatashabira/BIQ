from django import forms
from .models import UserTenantMembership
from tenants.models import Tenant
from django.contrib.auth import get_user_model

User = get_user_model()

class UserTenantMembershipForm(forms.ModelForm):
    tenant = forms.ModelChoiceField(queryset=Tenant.objects.all(), required=True)
    user = forms.ModelChoiceField(queryset=User.objects.all(), required=True)

    class Meta:
        model = UserTenantMembership
        fields = ['user', 'tenant']
