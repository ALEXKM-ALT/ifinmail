/**
 * <ifinmail-message-card> — reusable message card component.
 * Uses Shadow DOM for encapsulation. No framework.
 * Institutional Precision design: border-centric, flat-plus elevation.
 */
class IfinmailMessageCard extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
    }

    static get observedAttributes() {
        return ['sender', 'subject', 'snippet', 'date', 'unread', 'selected', 'message-id'];
    }

    connectedCallback() {
        this.render();
    }

    attributeChangedCallback() {
        this.render();
    }

    render() {
        const sender = this.getAttribute('sender') || '';
        const subject = this.getAttribute('subject') || '';
        const snippet = this.getAttribute('snippet') || '';
        const date = this.getAttribute('date') || '';
        const unread = this.hasAttribute('unread');
        const selected = this.hasAttribute('selected');

        const unreadBg = unread ? 'var(--ifinmail-bg-secondary, #eceef0)' : 'transparent';
        const selectedBg = selected ? 'var(--ifinmail-secondary-fixed-dim, #b4c5ff)' : unreadBg;
        const leftBorder = unread ? '3px solid var(--ifinmail-secondary, #0051d5)' : '3px solid transparent';
        const paddingLeft = unread
            ? 'calc(var(--ifinmail-space-4, 1rem) - 3px)'
            : 'var(--ifinmail-space-4, 1rem)';

        this.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: grid;
                    grid-template-columns: auto 1fr auto;
                    grid-template-rows: auto auto;
                    gap: 0 var(--ifinmail-space-3, 0.75rem);
                    padding: var(--ifinmail-space-3, 0.75rem) ${paddingLeft};
                    border-bottom: 1px solid var(--ifinmail-outline-variant, #c6c6cd);
                    border-left: ${leftBorder};
                    cursor: pointer;
                    background: ${selectedBg};
                }
                :host(:hover) {
                    background: var(--ifinmail-bg-secondary, #eceef0);
                }
                :host([selected]:hover) {
                    background: var(--ifinmail-secondary-fixed-dim, #b4c5ff);
                }
                .checkbox {
                    grid-row: 1 / -1;
                    align-self: center;
                    width: 16px;
                    height: 16px;
                    accent-color: var(--ifinmail-secondary, #0051d5);
                    flex-shrink: 0;
                    cursor: pointer;
                }
                .sender {
                    font-weight: 600;
                    grid-column: 2;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                .subject {
                    grid-column: 2;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                .snippet {
                    grid-column: 2;
                    color: var(--ifinmail-text-muted, #76777d);
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    font-size: 0.875rem;
                }
                .date {
                    grid-row: 1;
                    grid-column: 3;
                    justify-self: end;
                    font-size: 0.75rem;
                    color: var(--ifinmail-text-muted, #76777d);
                }
            </style>
            <input type="checkbox" class="checkbox" aria-label="Select message">
            <span class="sender">${this.escape(sender)}</span>
            <span class="subject">${this.escape(subject)}</span>
            <span class="snippet">${this.escape(snippet)}</span>
            <span class="date">${this.escape(date)}</span>
        `;

        const checkbox = this.shadowRoot.querySelector('.checkbox');
        checkbox.addEventListener('click', (e) => {
            e.stopPropagation();
        });

        this.addEventListener('click', () => {
            this.dispatchEvent(new CustomEvent('message-open', {
                bubbles: true,
                detail: { messageId: this.getAttribute('message-id') }
            }));
        });
    }

    escape(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

customElements.define('ifinmail-message-card', IfinmailMessageCard);
