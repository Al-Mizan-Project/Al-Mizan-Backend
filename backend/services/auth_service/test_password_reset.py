import re
from urllib.parse import parse_qs, urlparse

from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase

from auth_service.models import Role, Utilisateur


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_PASSWORD_RESET_URL="https://app.almizan.dz/reset-password",
)
class PasswordResetTests(APITestCase):
    def setUp(self):
        role = Role.objects.create(nom_role="ADMIN")
        self.user = Utilisateur.objects.create_user(
            email="admin@almizan.dz",
            password="ExistingPassword2026!",
            id_role=role,
        )

    def test_forgot_password_sends_localized_single_use_reset_links(self):
        cases = {
            "en": ("Reset your Al-Mizan password", "Reset link:"),
            "fr": ("Reinitialisation de votre mot de passe Al-Mizan", "Lien de reinitialisation:"),
            "ar": ("إعادة تعيين كلمة مرور الميزان", "رابط إعادة التعيين:"),
        }

        for index, (language, expected) in enumerate(cases.items(), start=1):
            with self.subTest(language=language):
                mail.outbox.clear()
                response = self.client.post(
                    "/auth/forgot-password",
                    {"email": self.user.email, "language": language},
                    format="json",
                )

                self.assertEqual(response.status_code, 200)
                self.assertNotIn("reset_token", response.data)
                self.assertEqual(len(mail.outbox), 1)
                self.assertEqual(mail.outbox[0].subject, expected[0])
                self.assertIn(expected[1], mail.outbox[0].body)

                reset_url = re.search(r"https://[^\s]+", mail.outbox[0].body).group(0)
                token = parse_qs(urlparse(reset_url).query)["token"][0]
                new_password = f"UpdatedPassword2026!{index}"
                reset_response = self.client.post(
                    "/auth/reset-password",
                    {"token": token, "new_password": new_password},
                    format="json",
                )

                self.assertEqual(reset_response.status_code, 204)
                self.user.refresh_from_db()
                self.assertTrue(self.user.check_password(new_password))
                self.assertNotEqual(self.user.password, new_password)

                reused_response = self.client.post(
                    "/auth/reset-password",
                    {"token": token, "new_password": "AnotherPassword2026!"},
                    format="json",
                )
                self.assertEqual(reused_response.status_code, 400)

    def test_forgot_password_defaults_to_french(self):
        response = self.client.post("/auth/forgot-password", {"email": self.user.email}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mail.outbox[0].subject, "Reinitialisation de votre mot de passe Al-Mizan")

    def test_forgot_password_rejects_unsupported_language(self):
        response = self.client.post(
            "/auth/forgot-password",
            {"email": self.user.email, "language": "de"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_unknown_email_has_same_response_without_email(self):
        response = self.client.post("/auth/forgot-password", {"email": "missing@almizan.dz"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
