"""Public registration flow — create profile, set password, verify email, choose username."""

import logging
import re
import time

from django.contrib.auth import login as auth_login
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from backend.apps.accounts.services import UserService
from backend.apps.domains.services import DomainService
from backend.apps.mail.services import MailService
from backend.services.audit import AuditService

logger = logging.getLogger('backend')
token_generator = PasswordResetTokenGenerator()

_RESERVED_USERNAMES: frozenset[str] = frozenset(
    {
        'admin',
        'root',
        'postmaster',
        'abuse',
        'noreply',
        'mailer-daemon',
        'hostmaster',
        'webmaster',
        'security',
        'support',
        'info',
        'help',
        'contact',
        'sales',
        'marketing',
        'spam',
        'mail',
        'email',
        'dmarc',
        'dkim',
        'spf',
        'bounce',
        'return',
        'mailer',
        'mta',
        'smtp',
        'imap',
        'pop3',
        'pop',
        'autodiscover',
        'autoconfig',
        'webmail',
        'cpanel',
        'whm',
        'plesk',
        'roundcube',
        'squirrelmail',
        'rainloop',
        'snappymail',
        'test',
        'dev',
        'stage',
        'staging',
        'prod',
        'production',
        'api',
        'www',
        'ftp',
        'ssh',
        'git',
        'mysql',
        'database',
        'server',
        'status',
        'health',
        'monitor',
        'alert',
        'team',
        'manager',
        'staff',
        'official',
        'ifinmail',
        'sysadmin',
        'administrator',
        'host',
        'dns',
        'ns1',
        'ns2',
        'mx',
        'mx1',
        'mx2',
        'cloud',
        'service',
    }
)


def _get_primary_domain() -> str:
    """Return the first configured domain name, or a default."""
    try:
        domains = DomainService.get_all_domains()
        if domains:
            return domains[0].name if hasattr(domains[0], 'name') else str(domains[0])
    except Exception:
        pass
    import os

    return os.environ.get('DOMAIN', '')


def _send_verification_email(request: HttpRequest, email: str) -> tuple[bool, str | None]:
    """Send a verification email with a signed token link.
    Returns (success, verify_url_or_None).
    """
    from smtplib import SMTPException

    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    user = user_model.objects.filter(email=email).first()
    if not user:
        return False, None
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_generator.make_token(user)
    verify_url = request.build_absolute_uri(f'/accounts/registration/verify/{uid}/{token}/')
    subject = 'Verify your email address'
    html_body = render_to_string(
        'registration/email_verify.html',
        {
            'verify_url': verify_url,
            'email': email,
        },
    )
    try:
        send_mail(subject, '', None, [email], html_message=html_body)
        return True, None
    except (SMTPException, ConnectionError, OSError) as e:
        logger.warning('Failed to send verification email to %s: %s', email, e)
        return False, verify_url


def step_profile(request: HttpRequest) -> HttpResponse:
    """Step 1: Collect email to create a profile."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        if not email:
            return render(
                request,
                'registration/step_profile.html',
                {
                    'error': 'Email is required.',
                },
            )
        if UserService.get_user_by_email(email):
            return render(
                request,
                'registration/step_profile.html',
                {
                    'error': 'An account with this email already exists.',
                    'email': email,
                },
            )
        request.session['reg_email'] = email
        return redirect('accounts:reg_password')
    return render(
        request,
        'registration/step_profile.html',
        {
            'email': request.session.get('reg_email', ''),
        },
    )


def step_password(request: HttpRequest) -> HttpResponse:
    """Step 2: Set a password for the account."""
    email = request.session.get('reg_email', '')
    if not email:
        return redirect('accounts:reg_profile')
    if request.method == 'POST':
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        if len(password) < 8:
            return render(
                request,
                'registration/step_password.html',
                {
                    'error': 'Password must be at least 8 characters.',
                },
            )
        if password != password2:
            return render(
                request,
                'registration/step_password.html',
                {
                    'error': 'Passwords do not match.',
                },
            )
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        try:
            user_model.objects.create_user(email=email, password=password, is_active=False)
            AuditService.record('registration_profile_created', user=email, severity='info')
        except IntegrityError:
            return render(
                request,
                'registration/step_password.html',
                {
                    'error': 'An account with this email already exists.',
                },
            )
        request.session['reg_user_created'] = True
        email_sent, verify_url = _send_verification_email(request, email)
        request.session['reg_email_sent'] = email_sent
        if not email_sent and verify_url:
            request.session['reg_verify_url'] = verify_url
        return redirect('accounts:reg_verify')
    return render(request, 'registration/step_password.html')


def step_verify(request: HttpRequest) -> HttpResponse:
    """Step 3: Show verification sent status with resend option."""
    email = request.session.get('reg_email', '') or request.POST.get('email', '')
    if not email:
        return redirect('accounts:reg_profile')
    if request.session.get('reg_verified'):
        return redirect('accounts:reg_username')
    error = None
    resent = False
    if request.method == 'POST' and request.POST.get('resend') == '1':
        last_sent = request.session.get('reg_resent_at', 0)
        if time.time() - last_sent < 60:
            error = 'Please wait at least 60 seconds before requesting another email.'
        else:
            ok, url = _send_verification_email(request, email)
            if ok:
                request.session['reg_resent_at'] = int(time.time())
                resent = True
                request.session.pop('reg_email_sent', None)
                request.session.pop('reg_verify_url', None)
            else:
                error = 'Could not send verification email. Please try again later.'
                if url:
                    request.session['reg_verify_url'] = url
    email_sent = request.session.get('reg_email_sent', True)
    fallback_url = request.session.get('reg_verify_url', None)
    return render(
        request,
        'registration/step_verify.html',
        {
            'email': email,
            'resent': resent,
            'error': error,
            'email_sent': email_sent,
            'fallback_url': fallback_url,
        },
    )


def step_verify_confirm(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    """Handle the verification link click — activate the user."""
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = user_model.objects.get(pk=uid)
    except (user_model.DoesNotExist, ValueError, TypeError):
        return render(
            request,
            'registration/step_verify.html',
            {
                'error': 'Invalid verification link.',
            },
        )
    if not token_generator.check_token(user, token):
        return render(
            request,
            'registration/step_verify.html',
            {
                'error': 'This verification link has expired. Request a new one.',
            },
        )
    user.is_active = True
    user.save()
    request.session['reg_email'] = user.email
    request.session['reg_verified'] = True
    AuditService.record('registration_verified', user=user.email, severity='info')
    return redirect('accounts:reg_username')


def step_username(request: HttpRequest) -> HttpResponse:
    """Step 4: Choose a username (local part) for the email address."""
    email = request.session.get('reg_email', '')
    if not email or not request.session.get('reg_verified'):
        return redirect('accounts:reg_profile')
    domain = _get_primary_domain()
    suggestion = email.split('@')[0].replace('.', '').lower()[:20]
    error = ''
    success = False
    chosen_username = ''
    if request.method == 'POST':
        chosen_username = request.POST.get('username', '').strip().lower()
        if not chosen_username:
            error = 'Please enter a username.'
        elif not re.match(r'^[a-z0-9][a-z0-9._-]{1,30}[a-z0-9]$', chosen_username):
            error = (
                'Username must be 3-32 characters, using letters, numbers, '
                'dots, hyphens, or underscores.'
            )
        elif chosen_username in _RESERVED_USERNAMES:
            error = 'This username is reserved and cannot be used.'
        else:
            try:
                if domain:
                    from backend.apps.domains.models import Domain

                    domain_obj = DomainService.get_domain_by_name(domain) or Domain(name=domain)
                    MailService.get_or_create_mailbox(domain=domain_obj, local_part=chosen_username)
                full_address = f'{chosen_username}@{domain}' if domain else chosen_username
                request.session['reg_username'] = chosen_username
                AuditService.record(
                    'registration_username_chosen', user=email, detail=full_address, severity='info'
                )
                success = True
            except IntegrityError:
                error = 'This username is already taken. Try another.'
            except Exception as e:
                logger.exception('Failed to create mailbox: %s', e)
                error = 'Could not create mailbox. Please try again.'
        if success:
            return redirect('accounts:reg_complete')
    return render(
        request,
        'registration/step_username.html',
        {
            'email': email,
            'domain': domain,
            'suggestion': suggestion,
            'error': error,
            'chosen': chosen_username or suggestion,
        },
    )


def step_complete(request: HttpRequest) -> HttpResponse:
    """Step 5: Registration complete — auto-login and redirect."""
    email = request.session.get('reg_email', '')
    username = request.session.get('reg_username', '')
    domain = _get_primary_domain()
    if not email:
        return redirect('accounts:reg_profile')

    # Auto-login the newly registered user
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    user = user_model.objects.filter(email=email, is_active=True).first()
    if user:
        auth_login(request, user)

    email_address = f'{username}@{domain}' if username and domain else email

    # clear session
    for key in [
        'reg_email',
        'reg_user_created',
        'reg_verified',
        'reg_username',
        'reg_email_sent',
        'reg_verify_url',
        'reg_resent_at',
    ]:
        request.session.pop(key, None)

    AuditService.record('registration_complete', user=email, detail=email_address, severity='info')
    return render(
        request,
        'registration/step_complete.html',
        {
            'email': email,
            'email_address': email_address,
        },
    )


def check_username_availability(request: HttpRequest) -> JsonResponse:
    """JSON endpoint for real-time username availability checking."""
    username = request.GET.get('username', '').strip().lower()
    if not username or not re.match(r'^[a-z0-9][a-z0-9._-]{1,30}[a-z0-9]$', username):
        return JsonResponse({'available': False, 'reason': 'invalid'})
    try:
        from backend.apps.mail.models import Mailbox

        taken = Mailbox.objects.filter(local_part=username).exists()
        return JsonResponse({'available': not taken})
    except Exception:
        return JsonResponse({'available': True})
