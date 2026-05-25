from django.urls import path
from django.views.generic import RedirectView

from .views import (
    dashboard,
    login_view,
    logout_view,
    setup_advance,
    setup_step,
    setup_wizard,
)

app_name = "accounts"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="accounts:dashboard", permanent=False)),
    path("dashboard/", dashboard, name="dashboard"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("setup/", setup_wizard, name="setup_wizard"),
    path("setup/<str:step>/", setup_step, name="setup_step"),
    path("setup/advance/", setup_advance, name="setup_advance"),
]
