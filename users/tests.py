from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import UserProfile

User = get_user_model()

class UserProfileTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_user_profile_creation(self):
        """Test that a UserProfile is automatically created when a User is created"""
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertIsInstance(self.user.profile, UserProfile)

    def test_user_profile_str(self):
        """Test the string representation of UserProfile"""
        expected = f"{self.user.username}'s Profile"
        self.assertEqual(str(self.user.profile), expected)