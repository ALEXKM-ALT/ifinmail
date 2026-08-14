(function() {
    'use strict';
    
    const signinCard = document.getElementById('signin-card');
    const forgotCard = document.getElementById('forgot-card');
    const twofactorCard = document.getElementById('twofactor-card');
    const createCard = document.getElementById('create-card');
    
    const signinForm = document.getElementById('signin-form');
    const forgotForm = document.getElementById('forgot-form');
    const twofactorForm = document.getElementById('twofactor-form');
    const createForm = document.getElementById('create-form');
    
    const signinBtn = document.getElementById('signin-btn');
    const forgotBtn = document.getElementById('forgot-btn');
    const twofactorBtn = document.getElementById('twofactor-btn');
    const createBtn = document.getElementById('create-btn');
    
    const signinError = document.getElementById('signin-error');
    const forgotError = document.getElementById('forgot-error');
    const forgotSuccess = document.getElementById('forgot-success');
    const twofactorError = document.getElementById('twofactor-error');
    const createError = document.getElementById('create-error');
    const createSuccess = document.getElementById('create-success');
    
    const forgotLink = document.getElementById('forgot-link');
    const backToSignin = document.getElementById('back-to-signin');
    const backToSigninCreate = document.getElementById('back-to-signin-create');
    const createAccountLink = document.getElementById('create-account-link');
    const resendCode = document.getElementById('resend-code');
    const countdown = document.getElementById('countdown');
    const countdownTimer = document.getElementById('countdown-timer');
    
    const togglePassword = document.getElementById('toggle-password');
    const passwordInput = document.getElementById('password');
    
    const USERS_KEY = 'ifinmail.users';
    let countdownInterval = null;
    let tempEmail = '';
    
    // Toggle password visibility
    togglePassword.addEventListener('click', function() {
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);
        togglePassword.setAttribute('aria-label', type === 'password' ? 'Show password' : 'Hide password');
    });
    
    document.querySelectorAll('.toggle-password[data-toggle-target]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const target = document.getElementById(btn.dataset.toggleTarget);
            const type = target.getAttribute('type') === 'password' ? 'text' : 'password';
            target.setAttribute('type', type);
            btn.setAttribute('aria-label', type === 'password' ? 'Show password' : 'Hide password');
        });
    });
    
    // Show forgot password screen
    forgotLink.addEventListener('click', function(e) {
        e.preventDefault();
        showCard('forgot');
    });
    
    // Show create account screen
    createAccountLink.addEventListener('click', function(e) {
        e.preventDefault();
        showCard('create');
    });
    
    // Back to sign in
    backToSignin.addEventListener('click', function(e) {
        e.preventDefault();
        showCard('signin');
        forgotForm.reset();
        forgotError.style.display = 'none';
        forgotSuccess.style.display = 'none';
    });
    
    // Back to sign in (from create account)
    backToSigninCreate.addEventListener('click', function(e) {
        e.preventDefault();
        showCard('signin');
        createForm.reset();
        hideError(createError);
        createSuccess.style.display = 'none';
    });
    
    // Sign In
    signinForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const email = document.getElementById('email').value.trim();
        const password = passwordInput.value;
        
        hideError(signinError);
        setLoading(signinBtn, true);
        
        // Simulate API call
        setTimeout(function() {
            setLoading(signinBtn, false);
            
            const createdUser = getCreatedUser(email);
            
            // Demo: Check if credentials match
            if ((email === 'alex@example.com' && password === 'password') ||
                (email === 'alex@ifinmail.com' && password === 'blaise7128') ||
                (email === 'admin@example.com' && password === 'admin123') ||
                (createdUser && createdUser.password === password)) {
                tempEmail = email;
                
                let session = null;
                if (createdUser) {
                    session = { name: createdUser.name, email: createdUser.email };
                } else if (email === 'alex@example.com') {
                    session = { name: 'Alex Mwangi', email: 'alex@example.com' };
                } else if (email === 'alex@ifinmail.com') {
                    session = { name: 'Alex Mwangi', email: 'alex@ifinmail.com' };
                } else if (email === 'admin@example.com') {
                    session = { name: 'Administrator', email: 'admin@example.com' };
                }
                if (session) localStorage.setItem('ifinmail.session', JSON.stringify(session));
                
                // Newly created accounts skip 2FA
                if (createdUser || email === 'alex@ifinmail.com') {
                    window.location.href = 'index.html';
                } else {
                    showCard('twofactor');
                    initOtpInputs();
                }
            } else {
                showError(signinError, 'Invalid email or password. Try alex@example.com / password');
            }
        }, 1000);
    });
    
    // Create Account
    createForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const name = document.getElementById('create-name').value.trim();
        const email = document.getElementById('create-email').value.trim().toLowerCase();
        const password = document.getElementById('create-password').value;
        const confirm = document.getElementById('create-confirm').value;
        const terms = document.getElementById('create-terms').checked;
        
        hideError(createError);
        createSuccess.style.display = 'none';
        
        if (!name) {
            showError(createError, 'Please enter your full name');
            return;
        }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            showError(createError, 'Please enter a valid email address');
            return;
        }
        if (password.length < 8) {
            showError(createError, 'Password must be at least 8 characters');
            return;
        }
        if (password !== confirm) {
            showError(createError, 'Passwords do not match');
            return;
        }
        if (!terms) {
            showError(createError, 'You must agree to the Terms of Service');
            return;
        }
        if (getCreatedUser(email)) {
            showError(createError, 'An account with this email already exists');
            return;
        }
        
        setLoading(createBtn, true);
        
        // Simulate API call
        setTimeout(function() {
            setLoading(createBtn, false);
            
            const users = getCreatedUsers();
            users.push({ name: name, email: email, password: password, createdAt: new Date().toISOString() });
            localStorage.setItem(USERS_KEY, JSON.stringify(users));
            
            createForm.reset();
            createSuccess.style.display = 'block';
            createSuccess.textContent = 'Account created. You can now sign in.';
            
            document.getElementById('email').value = email;
            
            setTimeout(function() {
                showCard('signin');
                createSuccess.style.display = 'none';
            }, 1500);
        }, 1200);
    });
    
    function getCreatedUsers() {
        try {
            return JSON.parse(localStorage.getItem(USERS_KEY)) || [];
        } catch (err) {
            return [];
        }
    }
    
    function getCreatedUser(email) {
        return getCreatedUsers().find(function(u) { return u.email === email; });
    }
    
    // Forgot Password
    forgotForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const email = document.getElementById('forgot-email').value.trim();
        
        hideError(forgotError);
        forgotSuccess.style.display = 'none';
        setLoading(forgotBtn, true);
        
        setTimeout(function() {
            setLoading(forgotBtn, false);
            forgotSuccess.style.display = 'block';
            forgotForm.reset();
        }, 1500);
    });
    
    // Two-Factor Authentication
    function initOtpInputs() {
        const inputs = document.querySelectorAll('.otp-input');
        inputs.forEach(function(input, index) {
            input.value = '';
            input.addEventListener('input', function(e) {
                const value = e.target.value.replace(/[^0-9]/g, '');
                e.target.value = value.slice(0, 1);
                
                if (value && index < inputs.length - 1) {
                    inputs[index + 1].focus();
                }
            });
            
            input.addEventListener('keydown', function(e) {
                if (e.key === 'Backspace' && !e.target.value && index > 0) {
                    inputs[index - 1].focus();
                }
            });
            
            input.addEventListener('paste', function(e) {
                e.preventDefault();
                const paste = (e.clipboardData || window.clipboardData).getData('text');
                const digits = paste.replace(/[^0-9]/g, '').slice(0, 6);
                
                digits.split('').forEach(function(digit, i) {
                    if (inputs[i]) {
                        inputs[i].value = digit;
                    }
                });
                
                const focusIndex = Math.min(digits.length, inputs.length - 1);
                inputs[focusIndex].focus();
            });
        });
        
        if (inputs.length > 0) {
            inputs[0].focus();
        }
    }
    
    twofactorForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const inputs = document.querySelectorAll('.otp-input');
        const code = Array.from(inputs).map(function(input) { return input.value; }).join('');
        
        hideError(twofactorError);
        setLoading(twofactorBtn, true);
        
        setTimeout(function() {
            setLoading(twofactorBtn, false);
            
            // Demo: Accept any 6-digit code
            if (code.length === 6) {
                // Success - redirect to main app
                window.location.href = 'index.html';
            } else {
                showError(twofactorError, 'Please enter a valid 6-digit code');
            }
        }, 1000);
    });
    
    // Resend code
    resendCode.addEventListener('click', function(e) {
        e.preventDefault();
        startCountdown();
    });
    
    function startCountdown() {
        let seconds = 30;
        countdown.style.display = 'block';
        resendCode.style.display = 'none';
        countdownTimer.textContent = seconds;
        
        if (countdownInterval) {
            clearInterval(countdownInterval);
        }
        
        countdownInterval = setInterval(function() {
            seconds--;
            countdownTimer.textContent = seconds;
            
            if (seconds <= 0) {
                clearInterval(countdownInterval);
                countdown.style.display = 'none';
                resendCode.style.display = 'inline';
            }
        }, 1000);
    }
    
    // Utility functions
    function showCard(card) {
        signinCard.classList.add('hidden');
        forgotCard.classList.add('hidden');
        twofactorCard.classList.add('hidden');
        createCard.classList.add('hidden');
        
        if (card === 'signin') {
            signinCard.classList.remove('hidden');
        } else if (card === 'forgot') {
            forgotCard.classList.remove('hidden');
        } else if (card === 'twofactor') {
            twofactorCard.classList.remove('hidden');
        } else if (card === 'create') {
            createCard.classList.remove('hidden');
        }
    }
    
    function showError(element, message) {
        element.textContent = message;
        element.style.display = 'block';
    }
    
    function hideError(element) {
        element.style.display = 'none';
        element.textContent = '';
    }
    
    function setLoading(button, isLoading) {
        const text = button.querySelector('.btn-text');
        const loader = button.querySelector('.btn-loader');
        
        button.disabled = isLoading;
        
        if (isLoading) {
            text.style.display = 'none';
            loader.style.display = 'inline-flex';
        } else {
            text.style.display = 'inline';
            loader.style.display = 'none';
        }
    }
    
    // Start countdown on 2FA page load
    startCountdown();
})();