pub mod crypto;
pub mod mail_parse;
pub mod policy;
pub mod sync;

pub use crypto::CryptoEngine;
pub use mail_parse::MailParser;
pub use policy::PolicyEngine;
pub use sync::SyncEngine;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoreConfig {
    pub secret_key: String,
    pub database_url: Option<String>,
    pub redis_url: Option<String>,
}

impl Default for CoreConfig {
    fn default() -> Self {
        Self {
            secret_key: String::new(),
            database_url: None,
            redis_url: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthStatus {
    pub engine: String,
    pub version: String,
    pub ok: bool,
}
