import logging

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class MailgunEmailBackend(BaseEmailBackend):
    """Envia e-mails do Django pela API HTTP do Mailgun."""

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = settings.MAILGUN_API_KEY
        domain = settings.MAILGUN_DOMAIN

        if not api_key or not domain:
            raise ImproperlyConfigured(
                "Configure MAILGUN_API_KEY e MAILGUN_DOMAIN no ambiente."
            )

        endpoint = (
            f"{settings.MAILGUN_API_URL}/v3/{domain}/messages"
        )
        enviados = 0

        for email in email_messages:
            dados = {
                "from": email.from_email or settings.DEFAULT_FROM_EMAIL,
                "to": ",".join(email.to),
                "subject": email.subject,
            }

            if email.content_subtype == "html":
                dados["html"] = email.body
            else:
                dados["text"] = email.body

            try:
                resposta = requests.post(
                    endpoint,
                    auth=("api", api_key),
                    data=dados,
                    timeout=15,
                )
                resposta.raise_for_status()
                enviados += 1
            except requests.RequestException:
                logger.exception("Falha ao enviar e-mail pelo Mailgun")
                if not self.fail_silently:
                    raise

        return enviados