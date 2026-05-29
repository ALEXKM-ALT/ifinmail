# ruff: noqa: E501

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'scratch' / 'playwright-auth-report'

CSS_FILES = [
    'ifinmail-variables.css',
    'ifinmail-reset.css',
    'ifinmail-utilities.css',
    'ifinmail-layout.css',
    'ifinmail-components.css',
    'ifinmail-admin.css',
]

VIEWPORTS = {
    'desktop': {'width': 1280, 'height': 800},
    'tablet': {'width': 768, 'height': 900},
    'mobile': {'width': 390, 'height': 844},
}


def css_links() -> str:
    return '\n'.join(
        f'<link rel="stylesheet" href="{(ROOT / "frontend" / "static" / "css" / name).as_uri()}">'
        for name in CSS_FILES
    )


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en" class="ifinmail-shell">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  {css_links()}
</head>
<body class="ifinmail-body">
  {body}
</body>
</html>
"""


PAGES = {
    'login': page(
        'Login',
        """
<div class="ifinmail-login">
  <div class="ifinmail-login-card ifinmail-fade-in">
    <div class="ifinmail-login-card__brand"><span class="ifinmail-login-card__logo">ifinmail</span></div>
    <h1 class="ifinmail-login-card__title">Welcome back</h1>
    <p class="ifinmail-login-card__subtitle">Sign in to your account</p>
    <form class="ifinmail-login-form">
      <div class="ifinmail-login-form__group">
        <label class="ifinmail-login-form__label" for="email">Email</label>
        <input id="email" class="ifinmail-login-form__input" placeholder="you@example.com">
      </div>
      <div class="ifinmail-login-form__group">
        <div class="ifinmail-login-form__label-row">
          <label class="ifinmail-login-form__label" for="password">Password</label>
          <a class="ifinmail-login-form__forgot" href="#">Forgot password?</a>
        </div>
        <input id="password" class="ifinmail-login-form__input" placeholder="Enter your password">
      </div>
      <div class="ifinmail-login-form__checkbox-row">
        <label class="ifinmail-login-form__checkbox-label"><input type="checkbox" class="ifinmail-login-form__checkbox"> Remember me</label>
      </div>
      <button class="ifinmail-btn ifinmail-btn--primary ifinmail-btn--full ifinmail-login-form__submit">Sign In</button>
    </form>
    <p class="ifinmail-login-card__terms">By signing in, you agree to our Terms and Privacy Policy.</p>
  </div>
  <p class="ifinmail-login-card__register">Don't have an account? <a href="#">Create account</a></p>
</div>
""",
    ),
    'password-reset': page(
        'Password reset',
        """
<div class="ifinmail-login">
  <div class="ifinmail-login-card">
    <div class="ifinmail-login-card__brand"><span class="ifinmail-login-card__logo">ifinmail</span></div>
    <h1 class="ifinmail-login-card__title">Forgot password?</h1>
    <p class="ifinmail-login-card__subtitle">Enter your email and we'll send you a reset link.</p>
    <form class="ifinmail-login-form">
      <div class="ifinmail-login-form__group">
        <label class="ifinmail-login-form__label" for="id_email">Email</label>
        <input id="id_email" class="ifinmail-login-form__input" placeholder="you@example.com">
      </div>
      <button class="ifinmail-btn ifinmail-btn--primary ifinmail-btn--full ifinmail-login-form__submit">Send Reset Link</button>
    </form>
  </div>
  <p class="ifinmail-login-card__register"><a href="#">Back to sign in</a></p>
</div>
""",
    ),
    'registration-profile': page(
        'Registration profile',
        """
<div class="ifinmail-reg">
  <div class="ifinmail-reg-card ifinmail-fade-in">
    <div class="ifinmail-reg-stepper"><div class="ifinmail-reg-stepper__steps">
      <div class="ifinmail-reg-stepper__step ifinmail-reg-stepper__step--active"><span class="ifinmail-reg-stepper__dot">1</span><span class="ifinmail-reg-stepper__label">Profile</span></div>
      <div class="ifinmail-reg-stepper__connector"></div>
      <div class="ifinmail-reg-stepper__step"><span class="ifinmail-reg-stepper__dot">2</span><span class="ifinmail-reg-stepper__label">Password</span></div>
      <div class="ifinmail-reg-stepper__connector"></div>
      <div class="ifinmail-reg-stepper__step"><span class="ifinmail-reg-stepper__dot">3</span><span class="ifinmail-reg-stepper__label">Verify</span></div>
    </div><div class="ifinmail-reg-stepper__counter">Step 1 of 5</div></div>
    <h1 class="ifinmail-reg-card__title">Create your profile</h1>
    <p class="ifinmail-reg-card__subtitle">Start with your email address. You'll set up the rest in a moment.</p>
    <div class="ifinmail-login-form__group">
      <label class="ifinmail-login-form__label" for="reg_email">Email address</label>
      <input id="reg_email" class="ifinmail-login-form__input" placeholder="you@example.com">
      <span class="ifinmail-field-hint">Valid email format</span>
    </div>
    <button class="ifinmail-btn ifinmail-btn--primary ifinmail-btn--full ifinmail-login-form__submit">Continue</button>
    <p class="ifinmail-reg-card__footer-link">Already have an account? <a href="#">Sign in</a></p>
  </div>
</div>
""",
    ),
    'registration-password': page(
        'Registration password',
        """
<div class="ifinmail-reg">
  <div class="ifinmail-reg-card ifinmail-fade-in">
    <div class="ifinmail-reg-stepper"><div class="ifinmail-reg-stepper__counter">Step 2 of 5</div></div>
    <h1 class="ifinmail-reg-card__title">Set a password</h1>
    <p class="ifinmail-reg-card__subtitle">Choose a strong password to protect your account.</p>
    <div class="ifinmail-login-form__group">
      <label class="ifinmail-login-form__label" for="password1">Password</label>
      <input id="password1" class="ifinmail-login-form__input" placeholder="At least 8 characters">
      <div class="ifinmail-reg-pw-meter"><div class="ifinmail-reg-pw-meter__bar"><div class="ifinmail-reg-pw-meter__fill" style="width: 55%"></div></div><span class="ifinmail-reg-pw-meter__text">Good</span></div>
      <ul class="ifinmail-pw-reqs">
        <li class="ifinmail-pw-reqs__item">At least 8 characters</li>
        <li class="ifinmail-pw-reqs__item">One lowercase letter</li>
        <li class="ifinmail-pw-reqs__item">One uppercase letter</li>
        <li class="ifinmail-pw-reqs__item">One number</li>
      </ul>
    </div>
    <div class="ifinmail-login-form__group">
      <label class="ifinmail-login-form__label" for="password2">Confirm password</label>
      <input id="password2" class="ifinmail-login-form__input" placeholder="Re-enter password">
    </div>
    <button class="ifinmail-btn ifinmail-btn--primary ifinmail-btn--full ifinmail-login-form__submit">Create Account</button>
  </div>
</div>
""",
    ),
    'registration-verify': page(
        'Registration verify',
        """
<div class="ifinmail-reg">
  <div class="ifinmail-reg-card ifinmail-fade-in">
    <div class="ifinmail-reg-stepper"><div class="ifinmail-reg-stepper__counter">Step 3 of 5</div></div>
    <div class="ifinmail-reg-icon">Mail</div>
    <h1 class="ifinmail-reg-card__title">Check your email</h1>
    <p class="ifinmail-reg-card__subtitle">We sent a verification link to <strong>person@example.com</strong>.</p>
    <div class="ifinmail-verify-tip">If you don't see it, check your spam folder.</div>
    <button class="ifinmail-btn ifinmail-btn--ghost ifinmail-btn--full">Resend email</button>
  </div>
  <p class="ifinmail-reg-card__footer-link"><a href="#">Use a different email</a></p>
</div>
""",
    ),
    'registration-username': page(
        'Registration username',
        """
<div class="ifinmail-reg">
  <div class="ifinmail-reg-card ifinmail-fade-in">
    <div class="ifinmail-reg-stepper"><div class="ifinmail-reg-stepper__counter">Step 4 of 5</div></div>
    <h1 class="ifinmail-reg-card__title">Choose your email address</h1>
    <p class="ifinmail-reg-card__subtitle">Pick the local part for your new email address.</p>
    <div class="ifinmail-reg-username-preview"><span class="ifinmail-reg-username-preview__part">person</span><span class="ifinmail-reg-username-preview__at">@</span><span>example.com</span></div>
    <div class="ifinmail-login-form__group">
      <label class="ifinmail-login-form__label" for="username">Username</label>
      <input id="username" class="ifinmail-login-form__input" placeholder="Enter username">
      <p class="ifinmail-setup-hint">Use letters, numbers, dots, hyphens, or underscores. 3-32 characters.</p>
    </div>
    <button class="ifinmail-btn ifinmail-btn--primary ifinmail-btn--full ifinmail-login-form__submit">Finish Setup</button>
  </div>
</div>
""",
    ),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    results = []

    for name, html in PAGES.items():
        (OUT / f'{name}.html').write_text(html, encoding='utf-8')

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for viewport_name, viewport in VIEWPORTS.items():
            page_instance = browser.new_page(viewport=viewport)
            for name in PAGES:
                page_instance.goto((OUT / f'{name}.html').as_uri(), wait_until='networkidle')
                page_instance.screenshot(path=OUT / f'{name}-{viewport_name}.png', full_page=True)
                metrics = page_instance.evaluate(
                    """() => {
                        const card = document.querySelector('.ifinmail-login-card, .ifinmail-reg-card');
                        const body = document.body;
                        const box = card.getBoundingClientRect();
                        return {
                            cardWidth: Math.round(box.width),
                            cardHeight: Math.round(box.height),
                            cardTop: Math.round(box.top),
                            bodyScrollWidth: body.scrollWidth,
                            bodyClientWidth: document.documentElement.clientWidth,
                            bodyScrollHeight: body.scrollHeight,
                            bodyClientHeight: document.documentElement.clientHeight
                        };
                    }"""
                )
                metrics['page'] = name
                metrics['viewport'] = viewport_name
                metrics['ok'] = (
                    metrics['bodyScrollWidth'] <= metrics['bodyClientWidth']
                    and metrics['cardWidth'] <= min(viewport['width'] - 24, 430)
                    and metrics['cardHeight'] <= viewport['height'] - 24
                    and metrics['cardTop'] >= 12
                )
                results.append(metrics)
            page_instance.close()
        browser.close()

    (OUT / 'metrics.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    failed = [result for result in results if not result['ok']]
    if failed:
        print(json.dumps(failed, indent=2))
        raise SystemExit(1)
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
