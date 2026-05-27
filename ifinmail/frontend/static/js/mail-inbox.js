/**
 * Inbox controller — renders message list, handles interactions.
 * Vanilla JS, no framework. Progressive enhancement.
 */
import { IfinmailAPI } from './ifinmail-api.js';

class InboxController {
    constructor(container, api) {
        this.container = container;
        this.api = api;
        this.page = 1;
        this.loading = false;
        this.hasMore = true;
        this.currentMailbox = 'INBOX';
        this.searchQuery = '';
        this.searchDebounce = null;

        this.init();
    }

    init() {
        this.messageList = this.container.querySelector('.ifinmail-message-cards');
        this.loadMoreTrigger = this.container.querySelector('.ifinmail-load-more');

        // Infinite scroll
        this.container.addEventListener('scroll', () => this.handleScroll());

        // Search input
        const searchInput = this.container.querySelector('.ifinmail-search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                clearTimeout(this.searchDebounce);
                this.searchDebounce = setTimeout(() => {
                    this.searchQuery = e.target.value.trim();
                    this.resetAndReload();
                }, 300);
            });
        }

        // Select all checkbox
        const selectAll = this.container.querySelector('#select-all');
        if (selectAll) {
            selectAll.addEventListener('change', (e) => {
                const checkboxes = this.messageList.querySelectorAll('.ifinmail-checkbox, input[type="checkbox"]');
                checkboxes.forEach(cb => { cb.checked = e.target.checked; });
            });
        }

        // Keyboard navigation
        this.container.addEventListener('keydown', (e) => this.handleKeyboard(e));

        // Load first page
        this.loadMessages();
    }

    async loadMessages() {
        if (this.loading || !this.hasMore) return;

        this.loading = true;
        this.showLoading(true);

        try {
            const data = await this.api.getMessages(this.currentMailbox, this.page);
            this.renderMessages(data.messages);
            this.hasMore = data.has_more;
            this.page++;
        } catch (error) {
            this.showError('Failed to load messages. Please try again.');
        } finally {
            this.loading = false;
            this.showLoading(false);
        }
    }

    renderMessages(messages) {
        const fragment = document.createDocumentFragment();

        for (const msg of messages) {
            const card = this.createMessageCard(msg);
            fragment.appendChild(card);
        }

        this.messageList.appendChild(fragment);
    }

    createMessageCard(msg) {
        const card = document.createElement('ifinmail-message-card');
        card.setAttribute('sender', msg.sender);
        card.setAttribute('subject', msg.subject);
        card.setAttribute('snippet', msg.snippet || '');
        card.setAttribute('date', this.formatDate(msg.received_at));
        card.setAttribute('message-id', msg.id);

        if (!msg.read) {
            card.setAttribute('unread', '');
        }

        // Listen for open event from the web component
        card.addEventListener('message-open', (e) => {
            this.openMessage(e.detail.messageId, card);
        });

        return card;
    }

    openMessage(messageId, card) {
        // Remove unread styling (optimistic update)
        card.removeAttribute('unread');

        // Update URL hash
        window.location.hash = `#message/${messageId}`;

        // Load into reading pane
        this.loadMessageDetail(messageId);
    }

    async loadMessageDetail(messageId) {
        const detailPane = document.querySelector('.ifinmail-message-detail');
        if (!detailPane) return;

        detailPane.classList.add('ifinmail-message-detail--loading');
        detailPane.innerHTML = '';

        try {
            const msg = await this.api.getMessage(messageId);
            detailPane.innerHTML = this.renderMessageDetail(msg);
        } catch (error) {
            detailPane.innerHTML = '<p class="ifinmail-error">Failed to load message.</p>';
        } finally {
            detailPane.classList.remove('ifinmail-message-detail--loading');
        }
    }

    renderMessageDetail(msg) {
        return `
            <div class="ifinmail-message-full">
                <h2 class="ifinmail-message-full-subject">${this.escapeHtml(msg.subject)}</h2>
                <div class="ifinmail-message-full-meta">
                    <span class="ifinmail-font-semibold">${this.escapeHtml(msg.sender)}</span>
                    <span class="ifinmail-text-secondary">to ${this.escapeHtml(msg.to.join(', '))}</span>
                    <span class="ifinmail-text-secondary">${this.formatDate(msg.received_at)}</span>
                </div>
                <div class="ifinmail-message-full-body">${this.escapeHtml(msg.body_text)}</div>
            </div>
        `;
    }

    handleScroll() {
        const { scrollTop, scrollHeight, clientHeight } = this.container;
        if (scrollHeight - scrollTop - clientHeight < 200) {
            this.loadMessages();
        }
    }

    handleKeyboard(e) {
        const cards = this.messageList.querySelectorAll('ifinmail-message-card');
        const focused = document.activeElement;
        const currentIndex = Array.from(cards).indexOf(focused);

        if (e.key === 'ArrowDown' || e.key === 'j') {
            e.preventDefault();
            const next = currentIndex < cards.length - 1 ? currentIndex + 1 : 0;
            cards[next]?.focus();
        }

        if (e.key === 'ArrowUp' || e.key === 'k') {
            e.preventDefault();
            const prev = currentIndex > 0 ? currentIndex - 1 : cards.length - 1;
            cards[prev]?.focus();
        }

        if (e.key === 'Enter' && focused?.tagName === 'IFINMAIL-MESSAGE-CARD') {
            e.preventDefault();
            focused.click();
        }
    }

    resetAndReload() {
        this.page = 1;
        this.hasMore = true;
        this.messageList.innerHTML = '';
        this.loadMessages();
    }

    switchMailbox(mailbox) {
        this.currentMailbox = mailbox;
        this.resetAndReload();
    }

    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    formatDate(isoString) {
        const date = new Date(isoString);
        const today = new Date();
        if (date.toDateString() === today.toDateString()) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }

    showLoading(visible) {
        const existing = this.container.querySelector('.ifinmail-loading');
        if (visible && !existing) {
            const loader = document.createElement('div');
            loader.className = 'ifinmail-loading';
            loader.textContent = 'Loading...';
            this.messageList.appendChild(loader);
        } else if (!visible && existing) {
            existing.remove();
        }
    }

    showError(message) {
        const error = document.createElement('div');
        error.className = 'ifinmail-error';
        error.textContent = message;
        this.messageList.appendChild(error);
    }
}

// Initialize when the DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('.ifinmail-message-list');
    if (!container) return;

    const api = new IfinmailAPI();
    new InboxController(container, api);
});

export { InboxController };
