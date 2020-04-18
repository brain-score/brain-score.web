from django.test import TestCase

from benchmarks.models import User


class UserTest(TestCase):
    def test_created_inactive(self):
        user = User.objects.create(email='test@test.com')
        self.assertFalse(user.is_active)
