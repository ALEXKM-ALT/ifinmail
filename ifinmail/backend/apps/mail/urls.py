from django.urls import path

from .views import inbox

app_name = "mail"

urlpatterns = [
    path("", inbox, name="inbox"),
]
