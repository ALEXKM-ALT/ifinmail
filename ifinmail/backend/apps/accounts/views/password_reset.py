"""Password reset views using Django's built-in auth flows."""

from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)


class CustomPasswordResetView(PasswordResetView):
    template_name = 'admin/password_reset_form.html'
    email_template_name = 'admin/password_reset_email.html'
    subject_template_name = 'admin/password_reset_subject.txt'
    success_url = '/accounts/password-reset/done/'


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'admin/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'admin/password_reset_confirm.html'
    success_url = '/accounts/password-reset/complete/'


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'admin/password_reset_complete.html'


password_reset = CustomPasswordResetView.as_view()
password_reset_done = CustomPasswordResetDoneView.as_view()
password_reset_confirm = CustomPasswordResetConfirmView.as_view()
password_reset_complete = CustomPasswordResetCompleteView.as_view()
