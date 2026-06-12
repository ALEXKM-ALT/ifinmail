use std::collections::HashMap;

use mail_parser::{parsers::MessageParser, Address, HeaderValue, Message, MimeHeaders};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParsedMail {
    pub message_id: Option<String>,
    pub from: Option<String>,
    pub to: Vec<String>,
    pub cc: Vec<String>,
    pub bcc: Vec<String>,
    pub reply_to: Option<String>,
    pub in_reply_to: Option<String>,
    pub references: Vec<String>,
    pub subject: Option<String>,
    pub date: Option<String>,
    pub body_text: Option<String>,
    pub body_html: Option<String>,
    pub attachments: Vec<ParsedAttachment>,
    pub headers: HashMap<String, String>,
    pub dkim_result: Option<String>,
    pub spf_result: Option<String>,
    pub size: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParsedAttachment {
    pub filename: Option<String>,
    pub content_type: Option<String>,
    pub content_id: Option<String>,
    pub size: usize,
    pub data: Vec<u8>,
    pub inline: bool,
}

pub struct MailParser;

impl MailParser {
    pub fn parse(raw: &[u8]) -> Result<ParsedMail, String> {
        let parser = MessageParser::new();
        let msg = parser.parse(raw).ok_or("Failed to parse message")?;

        let subject = msg.subject().map(|s| s.to_string());
        let message_id = msg.message_id().map(|s| s.to_string());
        let in_reply_to = msg.in_reply_to().map(|s| s.to_string());
        let references: Vec<String> = msg
            .references()
            .iter()
            .map(|r| r.to_string())
            .collect();

        let from = msg.from().and_then(|a| Self::addr_to_string(&a));
        let to = msg
            .to()
            .map(|addrs| Self::addr_list_to_strings(addrs))
            .unwrap_or_default();
        let cc = msg
            .cc()
            .map(|addrs| Self::addr_list_to_strings(addrs))
            .unwrap_or_default();
        let bcc = msg
            .bcc()
            .map(|addrs| Self::addr_list_to_strings(addrs))
            .unwrap_or_default();
        let reply_to = msg.reply_to().and_then(|a| Self::addr_to_string(&a));
        let date = msg.date().map(|d| d.to_string());

        let mut headers = HashMap::new();
        for (name, value) in msg.headers() {
            headers.insert(name.to_string(), Self::header_value_to_string(value));
        }

        let body_text = msg.body_text(0).map(|s| s.to_string());
        let body_html = msg.body_html(0).map(|s| s.to_string());

        let mut attachments = Vec::new();
        for part in msg.attachments() {
            attachments.push(ParsedAttachment {
                filename: part.attachment_name().map(|s| s.to_string()),
                content_type: part.content_type().map(|ct| format!("{ct}")),
                content_id: part.content_id().map(|s| s.to_string()),
                size: part.contents().len(),
                data: part.contents().to_vec(),
                inline: part.is_inline(),
            });
        }

        let size = raw.len();

        let dkim_result = headers
            .get("dkim-signature")
            .map(|_| "signed".to_string());
        let spf_result = headers
            .get("received-spf")
            .map(|_| "present".to_string());

        Ok(ParsedMail {
            message_id,
            from,
            to,
            cc,
            bcc,
            reply_to,
            in_reply_to,
            references,
            subject,
            date,
            body_text,
            body_html,
            attachments,
            headers,
            dkim_result,
            spf_result,
            size,
        })
    }

    pub fn extract_recipients(raw: &[u8]) -> Vec<String> {
        let parser = MessageParser::new();
        let msg = match parser.parse(raw) {
            Some(m) => m,
            None => return vec![],
        };

        let mut recipients = Vec::new();
        for addr_list in [msg.to(), msg.cc(), msg.bcc()].into_iter().flatten() {
            for addr in addr_list.iter() {
                if let Some(email) = addr.address() {
                    recipients.push(email.to_string());
                }
            }
        }
        recipients
    }

    pub fn extract_sender(raw: &[u8]) -> Option<String> {
        let parser = MessageParser::new();
        let msg = parser.parse(raw)?;
        msg.from()
            .and_then(|a| a.iter().next())
            .and_then(|a| a.address())
            .map(|s| s.to_string())
    }

    fn addr_to_string(addr: &Address) -> Option<String> {
        match addr {
            Address::Mailbox(mb) => mb.address().map(|a| a.to_string()),
            Address::Group(g) => g
                .addresses()
                .first()
                .and_then(|a| a.address())
                .map(|a| a.to_string()),
        }
    }

    fn addr_list_to_strings(addrs: &[Address]) -> Vec<String> {
        addrs
            .iter()
            .filter_map(|a| Self::addr_to_string(a))
            .collect()
    }

    fn header_value_to_string(value: &HeaderValue) -> String {
        match value {
            HeaderValue::Text(s) => s.to_string(),
            HeaderValue::Address(a) => Self::addr_to_string(a).unwrap_or_default(),
            HeaderValue::Timestamp(t) => t.to_string(),
            _ => format!("{value}"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_simple_email() {
        let raw = b"From: alice@example.com\r\n\
                     To: bob@example.com\r\n\
                     Subject: Hello\r\n\
                     Message-ID: <abc123@example.com>\r\n\
                     Date: Mon, 1 Jan 2024 12:00:00 +0000\r\n\
                     \r\n\
                     Hello, Bob!";
        let parsed = MailParser::parse(raw).unwrap();
        assert_eq!(parsed.from, Some("alice@example.com".to_string()));
        assert!(parsed.to.contains(&"bob@example.com".to_string()));
        assert_eq!(parsed.subject, Some("Hello".to_string()));
        assert!(parsed.body_text.is_some());
    }

    #[test]
    fn test_extract_recipients() {
        let raw = b"From: a@x.com\r\n\
                     To: b@x.com\r\n\
                     Cc: c@x.com\r\n\
                     Subject: test\r\n\
                     \r\n\
                     body";
        let recipients = MailParser::extract_recipients(raw);
        assert!(recipients.contains(&"b@x.com".to_string()));
        assert!(recipients.contains(&"c@x.com".to_string()));
        assert_eq!(recipients.len(), 2);
    }

    #[test]
    fn test_extract_sender() {
        let raw = b"From: alice@example.com\r\n\
                     To: bob@example.com\r\n\
                     Subject: test\r\n\
                     \r\n\
                     body";
        let sender = MailParser::extract_sender(raw);
        assert_eq!(sender, Some("alice@example.com".to_string()));
    }

    #[test]
    fn test_parse_multipart() {
        let raw = b"From: a@x.com\r\n\
                     To: b@x.com\r\n\
                     Subject: multipart\r\n\
                     MIME-Version: 1.0\r\n\
                     Content-Type: multipart/alternative; boundary=boundary\r\n\
                     \r\n\
                     --boundary\r\n\
                     Content-Type: text/plain\r\n\
                     \r\n\
                     plain text\r\n\
                     --boundary\r\n\
                     Content-Type: text/html\r\n\
                     \r\n\
                     <p>html</p>\r\n\
                     --boundary--";
        let parsed = MailParser::parse(raw).unwrap();
        assert_eq!(parsed.body_text, Some("plain text\n".to_string()));
        assert_eq!(parsed.body_html, Some("<p>html</p>\n".to_string()));
    }
}
