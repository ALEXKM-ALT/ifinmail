/**
 * API client for ifinmail — zero dependencies.
 * Matches the Django Ninja v1 API contract.
 */
const API_BASE = '/v1';

class IfinmailAPI {
    constructor(token = null) {
        this.token = token;
        this.csrfToken = null;
        this.timeout = 15000;
    }

    setToken(token) {
        this.token = token;
    }

    setCsrfToken(token) {
        this.csrfToken = token;
    }

    async request(method, path, body = null) {
        const headers = { 'Accept': 'application/json' };

        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        if (body) {
            headers['Content-Type'] = 'application/json';
        }

        if (this.csrfToken && method !== 'GET') {
            headers['X-CSRFToken'] = this.csrfToken;
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        try {
            const response = await fetch(`${API_BASE}${path}`, {
                method,
                headers,
                body: body ? JSON.stringify(body) : null,
                signal: controller.signal,
            });

            if (!response.ok) {
                let error;
                try {
                    error = await response.json();
                } catch {
                    throw new IfinmailError('unknown', response.statusText, response.status);
                }
                throw new IfinmailError(error.code, error.message, response.status);
            }

            return response.json();
        } catch (err) {
            if (err instanceof IfinmailError) throw err;
            if (err.name === 'AbortError') {
                throw new IfinmailError('timeout', 'Request timed out', 0);
            }
            throw new IfinmailError('network', err.message, 0);
        } finally {
            clearTimeout(timeoutId);
        }
    }

    get(path) { return this.request('GET', path); }
    post(path, body) { return this.request('POST', path, body); }
    put(path, body) { return this.request('PUT', path, body); }
    delete(path) { return this.request('DELETE', path); }

    // Auth API
    async login(email, password) {
        return this.post('/auth/login', { email, password });
    }

    async logout() {
        return this.post('/auth/logout');
    }

    // Mail API
    async getMailboxes() {
        return this.get('/mail/mailboxes');
    }

    async getMessages(mailbox = 'INBOX', page = 1, limit = 50) {
        return this.get(`/mail/messages?mailbox=${mailbox}&page=${page}&limit=${limit}`);
    }

    async getMessage(id) {
        return this.get(`/mail/messages/${id}`);
    }

    async sendMessage(data) {
        return this.post('/mail/messages', data);
    }

    async markRead(id) {
        return this.put(`/mail/messages/${id}/read`);
    }

    async markUnread(id) {
        return this.delete(`/mail/messages/${id}/read`);
    }

    async archiveMessage(id) {
        return this.post(`/mail/messages/${id}/archive`);
    }

    // Admin API
    async getDNSHealth(domainId) {
        return this.get(`/admin/domains/${domainId}/dns-health`);
    }

    async getStats() {
        return this.get('/admin/stats');
    }

    async getEvents(limit = 20) {
        return this.get(`/admin/events?limit=${limit}`);
    }
}

class IfinmailError extends Error {
    constructor(code, message, status) {
        super(message);
        this.code = code;
        this.status = status;
        this.name = 'IfinmailError';
    }
}

export { IfinmailAPI, IfinmailError };
