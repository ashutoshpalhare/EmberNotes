"""Privacy-conscious security event logging; never log note contents or credentials."""
import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

logger = logging.getLogger("accounts.security")


@receiver(user_logged_in, dispatch_uid="accounts.log_login_success")
def log_login_success(sender, request, user, **kwargs):
    logger.info("authentication_succeeded")


@receiver(user_login_failed, dispatch_uid="accounts.log_login_failure")
def log_login_failure(sender, credentials, request, **kwargs):
    logger.warning("authentication_failed")


@receiver(user_logged_out, dispatch_uid="accounts.log_logout")
def log_logout(sender, request, user, **kwargs):
    logger.info("authentication_ended")
