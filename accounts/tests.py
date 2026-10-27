from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Ember Notes <no-reply@example.com>",
)
class PasswordRecoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="recovery-user",
            email="recovery@example.com",
            password="Strong-test-password-482!",
        )

    def test_known_email_receives_reset_link(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": self.user.email},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)

    def test_unknown_email_uses_same_success_page_without_sending_mail(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "unknown@example.com"},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_form_and_completion_pages_render(self):
        self.assertEqual(self.client.get(reverse("password_reset")).status_code, 200)
        self.assertEqual(self.client.get(reverse("password_reset_done")).status_code, 200)
        self.assertEqual(self.client.get(reverse("password_reset_complete")).status_code, 200)
