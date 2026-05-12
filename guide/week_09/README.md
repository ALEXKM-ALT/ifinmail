# Week 9: Rust Fundamentals for ifinmail Core Components

**Month 3: Integration & Capstone | Days 49–54**

Rust is used for ifinmail's security-sensitive, performance-critical, and cross-platform components: mail parsing, MIME handling, cryptography, sync engine, policy engine, and shared libraries linking into Python (via pyo3), Android (via JNI), and desktop apps. This week covers Rust syntax, ownership, error handling, and the FFI bridge to Python.

---

## Learning Goals for the Week

By Sunday, you will be able to:

- Write Rust programs with ownership, borrowing, and lifetimes
- Use Cargo for dependency management and builds
- Parse MIME email messages with Rust crates
- Call Rust functions from Python via pyo3
- Understand why Rust is chosen for the ifinmail "shared core"

---

## Day 1 (Monday): Rust Installation, Syntax & Cargo

### Learning Objectives
- Install the Rust toolchain (rustup, rustc, cargo)
- Understand Rust's basic syntax: variables, types, functions, control flow
- Create and build a Cargo project
- Understand immutability-by-default and the `mut` keyword
- Use `cargo fmt`, `cargo clippy`, and `cargo test`

### Theory / Reading
- **Rust**: systems language with zero-cost abstractions, no garbage collector, memory safety at compile time
- **Cargo**: Rust's package manager and build system (like pip + venv + pytest combined)
- **Immutability**: variables are immutable by default; opt into mutability with `mut`
- **Expression-based**: almost everything is an expression that returns a value

### Practical Exercise
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
rustc --version
cargo --version

# Create first project
cargo new ifinmail-core
cd ifinmail-core
tree  # or ls -R
```

```rust
// ifinmail-core/src/main.rs
/// Day 1: Rust basics — variables, types, functions, control flow.

fn main() {
    // --- Variables: immutable by default ---
    let domain = "ifinmail.local";
    println!("Domain: {}", domain);
    // domain = "other.com";  // ERROR: cannot assign twice to immutable variable
    
    let mut counter = 0;  // mutable
    counter += 1;
    println!("Counter: {}", counter);
    
    // --- Basic types ---
    let port: u16 = 587;           // explicit type
    let tls_enabled = true;        // type inference
    let envelope_from = "alice@ifinmail.local";
    let envelope_to = vec!["bob@ifinmail.local", "carol@ifinmail.local"];
    
    println!("SMTP on port {}, TLS: {}", port, tls_enabled);
    
    // --- Structs (like dataclasses, but value types) ---
    #[derive(Debug)]
    struct EmailAddress {
        local_part: String,
        domain: String,
    }
    
    impl EmailAddress {
        fn new(address: &str) -> Option<Self> {
            let parts: Vec<&str> = address.splitn(2, '@').collect();
            if parts.len() != 2 {
                return None;
            }
            Some(EmailAddress {
                local_part: parts[0].to_string(),
                domain: parts[1].to_string(),
            })
        }
        
        fn full(&self) -> String {
            format!("{}@{}", self.local_part, self.domain)
        }
    }
    
    let addr = EmailAddress::new("alice@ifinmail.local").unwrap();
    println!("Parsed address: {}", addr.full());
    println!("Local part: {}, Domain: {}", addr.local_part, addr.domain);
    
    // --- Enums (tagged unions — powerful for mail states) ---
    #[derive(Debug, PartialEq)]
    enum DeliveryStatus {
        Queued,
        Delivered,
        Deferred { reason: String, retry_count: u32 },
        Bounced { code: u16, message: String },
    }
    
    let status = DeliveryStatus::Deferred {
        reason: "Connection timed out".into(),
        retry_count: 3,
    };
    println!("Status: {:?}", status);
    
    // --- Match (exhaustive pattern matching) ---
    match &status {
        DeliveryStatus::Queued => println!("Mail is waiting in queue"),
        DeliveryStatus::Delivered => println!("Mail was delivered"),
        DeliveryStatus::Deferred { reason, retry_count } => {
            println!("Deferred: {} (retry #{})", reason, retry_count);
        }
        DeliveryStatus::Bounced { code, message } => {
            println!("Bounced with {}: {}", code, message);
        }
    }
}
```

```bash
# Build and run
cargo run

# Check formatting and lint
cargo fmt
cargo clippy

# Run tests
cargo test
```

### Checkpoint Questions
1. What does Rust's immutability-by-default prevent that Python does not?
2. How are Rust enums different from Python enums? Why are they called "sum types"?
3. What does `cargo clippy` do that `cargo check` does not?
4. Why is `#[derive(Debug)]` needed on structs?

### Connection to ifinmail
Rust enums perfectly model email delivery states (queued, deferred, bounced, delivered). The ownership system prevents data races in the sync engine. Cargo's lockfile (`Cargo.lock`) delivers on the proposal's supply-chain security requirement.

---

## Day 2 (Tuesday): Ownership, Borrowing & Lifetimes

### Learning Objectives
- Understand Rust's ownership rules
- Use references (`&T`, `&mut T`) and borrowing
- Understand lifetimes and the borrow checker
- Know when to clone vs borrow vs use references

### Theory / Reading
- **Ownership rules**: (1) each value has exactly one owner, (2) when owner goes out of scope, value is dropped, (3) ownership can be moved
- **Borrowing**: `&T` = shared reference (multiple readers), `&mut T` = exclusive reference (one writer)
- **Lifetimes**: how the compiler ensures references are always valid
- **Clone vs Copy**: Clone is explicit/heavy; Copy is implicit/light (bitwise copy)

### Practical Exercise
```rust
// ifinmail-core/src/ownership.rs
// Day 2: Ownership, borrowing, and lifetimes applied to email data.

#[derive(Debug, Clone)]
struct RawMessage {
    id: String,
    raw_bytes: Vec<u8>,
}

#[derive(Debug)]
struct ParsedMessage {
    id: String,
    from: String,
    to: Vec<String>,
    subject: String,
    body_snippet: String,
}

/// Parse a raw message WITHOUT taking ownership.
/// Uses a reference (&) — caller still owns the RawMessage.
fn parse_message_borrow(msg: &RawMessage) -> Option<ParsedMessage> {
    let text = String::from_utf8_lossy(&msg.raw_bytes);
    let lines: Vec<&str> = text.lines().collect();
    
    // Simplified header parsing (real parser uses mailparse crate)
    let mut from = String::new();
    let mut subject = String::new();
    let mut body_start = 0;
    
    for (i, line) in lines.iter().enumerate() {
        if line.is_empty() {
            body_start = i + 1;
            break;
        }
        if let Some(val) = line.strip_prefix("From: ") {
            from = val.to_string();
        }
        if let Some(val) = line.strip_prefix("Subject: ") {
            subject = val.to_string();
        }
    }
    
    let body = lines[body_start..].join("\n");
    let snippet: String = body.chars().take(100).collect();
    
    Some(ParsedMessage {
        id: msg.id.clone(),
        from,
        to: vec!["unknown".into()],
        subject,
        body_snippet: snippet,
    })
}

/// Parse a message BY TAKING OWNERSHIP.
/// Caller cannot use the RawMessage after this.
fn parse_message_own(msg: RawMessage) -> Option<ParsedMessage> {
    parse_message_borrow(&msg)  // Still can borrow internally
    // msg is dropped here
}

/// Demonstrate lifetimes: which reference lives how long?
fn find_header_value<'a>(headers: &'a str, name: &str) -> Option<&'a str> {
    for line in headers.lines() {
        if let Some(rest) = line.strip_prefix(name) {
            return Some(rest.trim());
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_parse_message_borrowing() {
        let msg = RawMessage {
            id: "test-001".into(),
            raw_bytes: b"From: alice@ifinmail.local\r\nSubject: Hello\r\n\r\nThis is the body.".to_vec(),
        };
        
        // Borrow: msg is still usable after
        let parsed = parse_message_borrow(&msg);
        assert!(parsed.is_some());
        assert_eq!(parsed.unwrap().from, "alice@ifinmail.local");
        assert_eq!(msg.id, "test-001");  // msg still valid
        
        // Own: msg is moved and no longer usable
        let parsed2 = parse_message_own(msg);
        assert!(parsed2.is_some());
        // println!("{}", msg.id);  // ERROR: msg was moved
    }
    
    #[test]
    fn test_header_parsing_with_lifetimes() {
        let headers = "From: alice@ifinmail.local\r\nSubject: Test\r\nDate: Today\r\n";
        let subject = find_header_value(headers, "Subject: ");
        assert_eq!(subject, Some("Test"));
        // The returned reference is tied to 'headers' — compiler enforces this
    }
}

fn main() {
    println!("Run `cargo test` to verify ownership examples.");
}
```

### Checkpoint Questions
1. What happens if you try to use a variable after it has been moved?
2. Why can you have many `&T` references but only one `&mut T` at a time?
3. When should you `clone()` vs pass a reference?
4. What does the `'a` lifetime annotation communicate to the compiler?

### Connection to ifinmail
Mail parsing is memory-intensive. Rust's ownership model means the parser can read raw bytes, extract references into them, and never allocate unless necessary. The Python (pyo3) bridge must respect ownership boundaries — Rust data crossing into Python must be explicitly converted or managed.

---

## Day 3 (Wednesday): Error Handling, Collections & Iterators

### Learning Objectives
- Use `Result<T, E>` and `Option<T>` for error handling
- Use the `?` operator for error propagation
- Work with `Vec`, `HashMap`, `HashSet`, and iterators
- Write idiomatic iterator chains (map, filter, collect)

### Theory / Reading
- **Result**: `Ok(T)` for success, `Err(E)` for failure — no exceptions
- **`?` operator**: if `Ok`, unwrap; if `Err`, return early from the function
- **Iterators**: lazy, composable, zero-cost abstractions
- **serde**: serialize/deserialize Rust structs to/from JSON (critical for ifinmail API contracts)

### Practical Exercise
```rust
// ifinmail-core/src/mail_processing.rs
// Day 3: Error handling, iterators, and practical mail operations.

use std::collections::HashMap;

/// Custom error type for mail processing.
#[derive(Debug)]
enum MailError {
    InvalidAddress(String),
    EmptyMessage,
    ParseError(String),
    DeliveryFailed { code: u16, message: String },
}

impl std::fmt::Display for MailError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match self {
            MailError::InvalidAddress(addr) => write!(f, "Invalid address: {}", addr),
            MailError::EmptyMessage => write!(f, "Message has no content"),
            MailError::ParseError(msg) => write!(f, "Parse error: {}", msg),
            MailError::DeliveryFailed { code, message } => {
                write!(f, "Delivery failed ({}): {}", code, message)
            }
        }
    }
}

/// Validate an email address. Returns Ok(()) or Err.
fn validate_address(address: &str) -> Result<(), MailError> {
    if !address.contains('@') || address.len() < 5 {
        return Err(MailError::InvalidAddress(address.to_string()));
    }
    Ok(())
}

/// Count unique domains in a list of email addresses.
/// Uses iterators, HashMap, and the ? operator.
fn count_domains(addresses: &[String]) -> Result<HashMap<String, usize>, MailError> {
    let mut counts = HashMap::new();
    
    for addr in addresses {
        validate_address(addr)?;  // ? propagates error
        
        let domain = addr.split('@').nth(1).unwrap();  // Safe after validation
        *counts.entry(domain.to_string()).or_insert(0) += 1;
    }
    
    Ok(counts)
}

/// Filter a list of recipients to only those on allowed domains.
fn filter_allowed_recipients(
    recipients: &[String],
    allowed_domains: &[String],
) -> Vec<String> {
    recipients
        .iter()
        .filter(|addr| {
            addr.split('@')
                .nth(1)
                .map(|domain| allowed_domains.contains(&domain.to_string()))
                .unwrap_or(false)
        })
        .cloned()
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_validate_address() {
        assert!(validate_address("alice@ifinmail.local").is_ok());
        assert!(validate_address("invalid").is_err());
        assert!(validate_address("a@b").is_err());  // too short
    }
    
    #[test]
    fn test_count_domains() -> Result<(), MailError> {
        let addrs = vec![
            "alice@ifinmail.com".to_string(),
            "bob@ifinmail.com".to_string(),
            "carol@acme.com".to_string(),
        ];
        let counts = count_domains(&addrs)?;
        assert_eq!(counts.get("ifinmail.com"), Some(&2));
        assert_eq!(counts.get("acme.com"), Some(&1));
        Ok(())
    }
    
    #[test]
    fn test_count_domains_invalid() {
        let addrs = vec!["invalid".to_string()];
        assert!(count_domains(&addrs).is_err());
    }
    
    #[test]
    fn test_filter_recipients() {
        let recipients = vec![
            "alice@ifinmail.com".to_string(),
            "bob@spam.net".to_string(),
            "carol@ifinmail.com".to_string(),
        ];
        let allowed = vec!["ifinmail.com".to_string()];
        
        let filtered = filter_allowed_recipients(&recipients, &allowed);
        assert_eq!(filtered.len(), 2);
        assert!(filtered.contains(&"alice@ifinmail.com".to_string()));
        assert!(!filtered.contains(&"bob@spam.net".to_string()));
    }
}
```

### Checkpoint Questions
1. How does Rust's `Result` type differ from Python's try/except?
2. What does the `?` operator do? How does it compare to `unwrap()`?
3. Why are Rust iterators described as "zero-cost abstractions"?
4. How would you parse a list of email flags using iterators?

### Connection to ifinmail
Error handling in the mail stack must be explicit — you cannot silently ignore a failed delivery. `Result<T, E>` makes error paths visible and enforced. Iterators process recipient lists, filter spam, and aggregate deliverability stats without allocating intermediate collections.

---

## Day 4 (Thursday): Cargo Dependencies & Mail Parsing Crates

### Learning Objectives
- Use external crates: `mailparse`, `serde`, `serde_json`
- Parse real MIME email messages
- Extract headers, body parts, and attachments
- Serialize parsed data to JSON (the format the Python API expects)

### Theory / Reading
- **mailparse crate**: MIME parsing library; handles multipart, quoted-printable, base64
- **serde**: the standard Rust serialization framework
- **Cargo.toml**: dependencies, features, edition, versioning
- **Semver in Cargo**: `^1.2.3` = compatible with 1.x.x; `=1.2.3` = exact

### Practical Exercise
```toml
# Cargo.toml additions
[package]
name = "ifinmail-core"
version = "0.1.0"
edition = "2021"

[dependencies]
mailparse = "0.15"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

```rust
// ifinmail-core/src/mail_parser.rs
/// MIME email parsing using the `mailparse` crate.
/// This is the core mail parsing functionality referenced in
/// proposal Section 10.2: "Mail parsing, MIME handling."

use mailparse::*;
use serde::{Deserialize, Serialize};
use std::fs;

#[derive(Debug, Serialize, Deserialize)]
struct ParsedEmail {
    subject: String,
    from: String,
    to: Vec<String>,
    cc: Vec<String>,
    date: String,
    message_id: String,
    body_text: String,
    body_html: Option<String>,
    attachments: Vec<AttachmentInfo>,
}

#[derive(Debug, Serialize, Deserialize)]
struct AttachmentInfo {
    filename: String,
    content_type: String,
    size_bytes: usize,
}

/// Parse a raw RFC 5322 / MIME email string into structured data.
fn parse_email(raw: &[u8]) -> Result<ParsedEmail, String> {
    let parsed = parse_mail(raw).map_err(|e| format!("Parse error: {}", e))?;
    
    let headers = parsed.get_headers();
    let subject = get_header_value(&headers, "Subject");
    let from = get_header_value(&headers, "From");
    let to = get_header_values(&headers, "To");
    let cc = get_header_values(&headers, "Cc");
    let date = get_header_value(&headers, "Date");
    let message_id = get_header_value(&headers, "Message-ID");
    
    let mut body_text = String::new();
    let mut body_html: Option<String> = None;
    let mut attachments = Vec::new();
    
    // Walk MIME parts
    walk_parts(&parsed, &mut body_text, &mut body_html, &mut attachments)
        .map_err(|e| format!("MIME error: {}", e))?;
    
    Ok(ParsedEmail {
        subject,
        from,
        to,
        cc,
        date,
        message_id,
        body_text,
        body_html,
        attachments,
    })
}

fn get_header_value(headers: &[MailHeader], name: &str) -> String {
    headers
        .iter()
        .find(|h| h.get_key_ref().eq_ignore_ascii_case(name))
        .map(|h| h.get_value())
        .unwrap_or_default()
}

fn get_header_values(headers: &[MailHeader], name: &str) -> Vec<String> {
    headers
        .iter()
        .filter(|h| h.get_key_ref().eq_ignore_ascii_case(name))
        .flat_map(|h| h.get_value().split(',').map(|s| s.trim().to_string()).collect::<Vec<_>>())
        .collect()
}

fn walk_parts(
    part: &ParsedMail,
    body_text: &mut String,
    body_html: &mut Option<String>,
    attachments: &mut Vec<AttachmentInfo>,
) -> Result<(), String> {
    if part.subparts.is_empty() {
        // Leaf part
        let ctype = part.ctype.mimetype.clone();
        let data = part.get_body_raw().unwrap_or_default();
        
        if ctype == "text/plain" {
            *body_text = part.get_body().unwrap_or_default();
        } else if ctype == "text/html" {
            *body_html = Some(part.get_body().unwrap_or_default());
        } else {
            // Attachment
            let filename = part.ctype.params.get("name")
                .or_else(|| part.content_disposition.params.get("filename"))
                .cloned()
                .unwrap_or_else(|| "unnamed".to_string());
            
            attachments.push(AttachmentInfo {
                filename,
                content_type: ctype,
                size_bytes: data.len(),
            });
        }
    } else {
        // Multipart — recurse into children
        for subpart in &part.subparts {
            walk_parts(subpart, body_text, body_html, attachments)?;
        }
    }
    
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_parse_simple_email() {
        let raw = b"\
From: Alice <alice@ifinmail.local>\r\n\
To: Bob <bob@ifinmail.local>\r\n\
Subject: Hello from ifinmail\r\n\
Date: Sun, 12 May 2024 10:00:00 +0000\r\n\
Message-ID: <abc123@ifinmail.local>\r\n\
Content-Type: text/plain; charset=utf-8\r\n\
\r\n\
This is a test message.\r\n\
Welcome to ifinmail!\r\n\
";
        let parsed = parse_email(raw).expect("Should parse");
        assert_eq!(parsed.subject, "Hello from ifinmail");
        assert_eq!(parsed.from, "Alice <alice@ifinmail.local>");
        assert!(parsed.to.contains(&"Bob <bob@ifinmail.local>".to_string()));
        assert_eq!(parsed.body_text.trim(), "This is a test message.\nWelcome to ifinmail!");
        assert!(parsed.body_html.is_none());
        assert!(parsed.attachments.is_empty());
    }
    
    #[test]
    fn test_output_json() {
        let raw = b"From: alice@ifinmail.local\r\nSubject: Test\r\n\r\nBody\r\n";
        let parsed = parse_email(raw).unwrap();
        let json = serde_json::to_string_pretty(&parsed).unwrap();
        println!("{}", json);
        assert!(json.contains("\"subject\""));
        assert!(json.contains("\"from\""));
    }
}
```

### Checkpoint Questions
1. How does `mailparse` handle multipart MIME messages?
2. What is the difference between `text/plain` and `text/html` MIME types?
3. Why serialize parsed email to JSON? Who consumes this data?
4. How does Cargo.lock support the proposal's supply-chain security goal?

### Connection to ifinmail
This Rust parser is one of the "shared secure core components" from proposal Section 10.2. The Python API can call it via pyo3 (tomorrow's topic). The Android app can call it via JNI. Desktop apps call it natively. One parser, no duplication.

---

## Day 5 (Friday): Python ↔ Rust Integration with pyo3

### Learning Objectives
- Create a Rust library callable from Python
- Use `pyo3` to expose Rust functions as Python modules
- Pass complex data structures between Python and Rust
- Understand the performance and safety boundaries

### Theory / Reading
- **pyo3**: Rust crate for Python bindings; two-way interop
- **GIL**: Python's Global Interpreter Lock — Rust code releases it for parallelism
- **Conversion cost**: crossing the FFI boundary costs CPU; batch operations when possible
- **Proposal Section 10.3**: integration between Python services and Rust libraries

### Practical Exercise
```bash
# Create the pyo3 library
cargo new --lib ifinmail-py
cd ifinmail-py
```

```toml
# ifinmail-py/Cargo.toml
[package]
name = "ifinmail_py"
version = "0.1.0"
edition = "2021"

[lib]
name = "ifinmail_py"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.22", features = ["extension-module"] }
mailparse = "0.15"
```

```rust
// ifinmail-py/src/lib.rs
/// Python-callable Rust functions for ifinmail.
/// Exposes mail parsing, validation, and policy checks to the Python API layer.
use pyo3::prelude::*;
use pyo3::types::PyDict;

/// Parse a raw email (bytes) and return a Python dict.
/// This is called from the FastAPI mail ingestion handler.
#[pyfunction]
fn parse_raw_email(py: Python<'_>, raw_bytes: &[u8]) -> PyResult<PyObject> {
    // Use mailparse to parse
    let parsed = mailparse::parse_mail(raw_bytes)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Parse error: {}", e)))?;
    
    // Build Python dict
    let result = PyDict::new(py);
    
    // Extract headers
    let headers = parsed.get_headers();
    result.set_item("subject", get_header(&headers, "Subject"))?;
    result.set_item("from", get_header(&headers, "From"))?;
    result.set_item("to", get_header(&headers, "To"))?;
    result.set_item("date", get_header(&headers, "Date"))?;
    
    // Body text
    if let Ok(body) = parsed.get_body() {
        result.set_item("body_text", body)?;
    }
    
    // Attachments
    let attachments: Vec<String> = parsed.subparts.iter()
        .filter(|p| p.ctype.mimetype != "text/plain" && p.ctype.mimetype != "text/html")
        .map(|p| {
            p.ctype.params.get("name")
                .cloned()
                .unwrap_or_else(|| "unnamed".to_string())
        })
        .collect();
    result.set_item("attachments", attachments)?;
    
    Ok(result.into())
}

/// Validate an email address — fast, callable from Python.
#[pyfunction]
fn is_valid_address(address: &str) -> bool {
    address.contains('@') 
        && address.len() >= 5
        && !address.starts_with('@')
        && !address.ends_with('@')
}

/// Check if a sender exceeds rate limits (trust-level based).
/// Returns (allowed: bool, reason: Option<String>).
#[pyfunction]
fn check_send_policy(
    trust_level: u8,
    sends_last_hour: u32,
    sends_last_day: u32,
) -> (bool, Option<String>) {
    // Matches proposal Section 6.2 trust levels
    let (hourly_limit, daily_limit) = match trust_level {
        0 => (5, 10),     // New unverified
        1 => (50, 200),   // Verified user
        2 => (200, 1000), // Healthy history
        3 => (500, 5000), // Business verified
        4 => (0, 0),      // Unlimited (dedicated plan)
        _ => (5, 10),
    };
    
    if trust_level == 4 {
        return (true, None);  // Unlimited
    }
    
    if sends_last_hour >= hourly_limit {
        return (false, Some(format!(
            "Hourly limit reached: {}/{}",
            sends_last_hour, hourly_limit
        )));
    }
    
    if sends_last_day >= daily_limit {
        return (false, Some(format!(
            "Daily limit reached: {}/{}",
            sends_last_day, daily_limit
        )));
    }
    
    (true, None)
}

fn get_header(headers: &[mailparse::MailHeader], name: &str) -> String {
    headers.iter()
        .find(|h| h.get_key_ref().eq_ignore_ascii_case(name))
        .map(|h| h.get_value())
        .unwrap_or_default()
}

/// The module definition — what Python sees when it does `import ifinmail_py`
#[pymodule]
fn ifinmail_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_raw_email, m)?)?;
    m.add_function(wrap_pyfunction!(is_valid_address, m)?)?;
    m.add_function(wrap_pyfunction!(check_send_policy, m)?)?;
    m.add("__version__", "0.1.0")?;
    Ok(())
}
```

```bash
# Build the Python extension
cd ifinmail-py
python3 -m venv venv
source venv/bin/activate
pip install maturin

# Build and install in development mode
maturin develop

# Test from Python
python3 << 'EOF'
import ifinmail_py

# Test address validation
print("Valid addresses:")
for addr in ["alice@ifinmail.com", "invalid", "", "@bad.com"]:
    print(f"  {addr:30s} → {ifinmail_py.is_valid_address(addr)}")

# Test send policy (trust level 1, 10 sends in last hour)
allowed, reason = ifinmail_py.check_send_policy(1, 10, 50)
print(f"\nSend policy (trust=1, hour=10, day=50): allowed={allowed}, reason={reason}")

# Test send policy violation (trust level 0, 6 sends in last hour)
allowed, reason = ifinmail_py.check_send_policy(0, 6, 10)
print(f"Send policy (trust=0, hour=6, day=10): allowed={allowed}, reason={reason}")

# Test email parsing
raw = b"From: alice@ifinmail.local\r\nSubject: Test from Rust!\r\n\r\nBody text here.\r\n"
parsed = ifinmail_py.parse_raw_email(raw)
print(f"\nParsed email: {parsed}")
EOF
```

### Checkpoint Questions
1. What is the performance cost of crossing the Python ↔ Rust FFI boundary?
2. Why batch operations at the FFI boundary instead of calling Rust once per small task?
3. How does pyo3 handle Python's GIL during Rust function execution?
4. Where in the ifinmail architecture would you place the Python ↔ Rust boundary?

### Connection to ifinmail
The `check_send_policy` function implements proposal Section 6.2 trust levels directly in Rust — fast, correct, and shared across every API endpoint that sends mail. The `parse_raw_email` function is called by the FastAPI ingestion handler. This is proposal Section 10.3 integration in practice.

---

## Day 6 (Saturday): Review & Integration

### Review Challenge: Rust Mail Ingestion Microservice

Build a complete mail ingestion pipeline:

1. **Rust library** (`ifinmail-core`): parses raw MIME, validates addresses, checks send policy
2. **Python FastAPI endpoint**: receives raw email bytes, calls Rust parser via pyo3, stores metadata in PostgreSQL
3. **Test harness**: sends a batch of sample emails through the pipeline
4. **Benchmark**: compare Rust-based parsing vs pure Python

**Stretch goal**: Add DKIM signature verification in Rust.

### Week 9 Self-Assessment

Before moving to Week 10, confirm you can:
- [ ] Write Rust programs with structs, enums, impl blocks, and match expressions
- [ ] Explain ownership, borrowing, and lifetimes
- [ ] Use `Result<T, E>` and the `?` operator for error handling
- [ ] Parse MIME emails with the `mailparse` crate
- [ ] Expose Rust functions to Python via pyo3
- [ ] Explain where Rust adds value in the ifinmail stack vs Python

---

## Week 9 Resource Index

| Resource | Location |
|---|---|
| Rust installation guide | `references/rust_setup.md` |
| Ownership cheat sheet | `references/rust_ownership.md` |
| mailparse crate docs | `references/mailparse_guide.md` |
| pyo3 integration guide | `references/pyo3_guide.md` |
| Cargo.toml reference | `references/cargo_reference.md` |
| Code: ifinmail-core | `code/ifinmail-core/` |
| Code: ifinmail-py | `code/ifinmail-py/` |

---

*Week 9 of 12 — Rust Fundamentals for ifinmail Platform Engineering*
