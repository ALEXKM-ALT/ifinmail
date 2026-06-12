use std::collections::HashMap;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncState {
    pub device_id: String,
    pub last_sync: DateTime<Utc>,
    pub cursor: Option<String>,
    pub mailbox_id: String,
    pub known_uids: Vec<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncDelta {
    pub new_messages: Vec<SyncMessage>,
    pub updated_uids: Vec<u64>,
    pub deleted_uids: Vec<u64>,
    pub new_cursor: String,
    pub has_more: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncMessage {
    pub uid: u64,
    pub message_id: String,
    pub subject: Option<String>,
    pub from: Option<String>,
    pub to: Vec<String>,
    pub date: Option<DateTime<Utc>>,
    pub flags: Vec<String>,
    pub folder: String,
    pub size: usize,
}

pub struct SyncEngine {
    db_url: String,
}

impl SyncEngine {
    pub fn new(db_url: &str) -> Self {
        Self {
            db_url: db_url.to_string(),
        }
    }

    pub fn initial_state(device_id: &str, mailbox_id: &str) -> SyncState {
        SyncState {
            device_id: device_id.to_string(),
            last_sync: Utc::now(),
            cursor: None,
            mailbox_id: mailbox_id.to_string(),
            known_uids: vec![],
        }
    }

    pub fn compute_delta(current_uidv: u64, known_uids: &[u64], server_uids: &[u64]) -> SyncDelta {
        let known: std::collections::HashSet<u64> = known_uids.iter().copied().collect();
        let server: std::collections::HashSet<u64> = server_uids.iter().copied().collect();

        let new_uids: Vec<u64> = server.difference(&known).copied().collect();
        let deleted_uids: Vec<u64> = known.difference(&server).copied().collect();

        SyncDelta {
            new_messages: vec![],
            updated_uids: new_uids,
            deleted_uids,
            new_cursor: format!("{current_uidv}:{}", Utc::now().timestamp()),
            has_more: false,
        }
    }

    pub fn batch_uids(uids: &[u64], batch_size: usize) -> Vec<Vec<u64>> {
        uids.chunks(batch_size).map(|chunk| chunk.to_vec()).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_initial_state() {
        let state = SyncEngine::initial_state("device-1", "mailbox-1");
        assert_eq!(state.device_id, "device-1");
        assert_eq!(state.mailbox_id, "mailbox-1");
        assert!(state.known_uids.is_empty());
    }

    #[test]
    fn test_delta_new_messages() {
        let known = vec![1, 2, 3];
        let server = vec![1, 2, 3, 4, 5];
        let delta = SyncEngine::compute_delta(5, &known, &server);
        assert_eq!(delta.updated_uids, vec![4, 5]);
        assert!(delta.deleted_uids.is_empty());
    }

    #[test]
    fn test_delta_deleted_messages() {
        let known = vec![1, 2, 3, 4, 5];
        let server = vec![1, 2, 3];
        let delta = SyncEngine::compute_delta(3, &known, &server);
        assert!(delta.updated_uids.is_empty());
        let mut deleted = delta.deleted_uids;
        deleted.sort();
        assert_eq!(deleted, vec![4, 5]);
    }

    #[test]
    fn test_delta_empty() {
        let known = vec![1, 2, 3];
        let delta = SyncEngine::compute_delta(3, &known, &known);
        assert!(delta.updated_uids.is_empty());
        assert!(delta.deleted_uids.is_empty());
    }

    #[test]
    fn test_batch_uids() {
        let uids: Vec<u64> = (1..=100).collect();
        let batches = SyncEngine::batch_uids(&uids, 30);
        assert_eq!(batches.len(), 4);
        assert_eq!(batches[0].len(), 30);
        assert_eq!(batches[3].len(), 10);
    }
}
