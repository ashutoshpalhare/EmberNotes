import logging

from django.contrib.auth import login
from django.shortcuts import redirect, render
from django_ratelimit.decorators import ratelimit

from .forms import SignupForm

security_logger = logging.getLogger("accounts.security")


@ratelimit(key="ip", rate="5/h", method="POST", block=True)
def signup(request):
    if request.user.is_authenticated:
        return redirect("notes:list")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        security_logger.info("account_signup_succeeded")
        return redirect("notes:list")
    return render(request, "registration/signup.html", {"form": form})
