use aes_gcm::aead::{Aead, KeyInit, OsRng};
use aes_gcm::{Aes256Gcm, Nonce};
use argon2::Argon2;
use rand::RngCore;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use thiserror::Error;

const NONCE_LEN: usize = 12;
const SALT_LEN: usize = 16;
const KEY_LEN: usize = 32;

#[derive(Error, Debug)]
pub enum CryptoError {
    #[error("Encryption failed: {0}")]
    EncryptFailed(String),
    #[error("Decryption failed: {0}")]
    DecryptFailed(String),
    #[error("Invalid key: {0}")]
    InvalidKey(String),
    #[error("Hash verification failed")]
    HashMismatch,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptedPayload {
    pub ciphertext: Vec<u8>,
    pub nonce: Vec<u8>,
    pub salt: Vec<u8>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CryptoEngine {
    master_key: Vec<u8>,
}

impl CryptoEngine {
    pub fn new(secret: &str) -> Self {
        let key = Sha256::digest(secret.as_bytes());
        Self {
            master_key: key.to_vec(),
        }
    }

    pub fn derive_key(&self, salt: &[u8]) -> Result<Vec<u8>, CryptoError> {
        let mut key = vec![0u8; KEY_LEN];
        Argon2::default()
            .hash_password_into(&self.master_key, salt, &mut key)
            .map_err(|e| CryptoError::InvalidKey(e.to_string()))?;
        Ok(key)
    }

    pub fn encrypt(&self, plaintext: &[u8]) -> Result<EncryptedPayload, CryptoError> {
        let mut salt = vec![0u8; SALT_LEN];
        OsRng.fill_bytes(&mut salt);
        let key = self.derive_key(&salt)?;
        let cipher = Aes256Gcm::new_from_slice(&key)
            .map_err(|e| CryptoError::InvalidKey(e.to_string()))?;
        let mut nonce = vec![0u8; NONCE_LEN];
        OsRng.fill_bytes(&mut nonce);
        let nonce = Nonce::from_slice(&nonce);
        let ciphertext = cipher
            .encrypt(nonce, plaintext)
            .map_err(|e| CryptoError::EncryptFailed(e.to_string()))?;

        Ok(EncryptedPayload {
            ciphertext,
            nonce: nonce.to_vec(),
            salt,
        })
    }

    pub fn decrypt(&self, payload: &EncryptedPayload) -> Result<Vec<u8>, CryptoError> {
        let key = self.derive_key(&payload.salt)?;
        let cipher = Aes256Gcm::new_from_slice(&key)
            .map_err(|e| CryptoError::InvalidKey(e.to_string()))?;
        let nonce = Nonce::from_slice(&payload.nonce);
        cipher
            .decrypt(nonce, payload.ciphertext.as_ref())
            .map_err(|e| CryptoError::DecryptFailed(e.to_string()))
    }

    pub fn hash_password(password: &str) -> Result<String, CryptoError> {
        let salt = uuid::Uuid::new_v4().to_string();
        let mut hash = vec![0u8; 32];
        Argon2::default()
            .hash_password_into(password.as_bytes(), salt.as_bytes(), &mut hash)
            .map_err(|e| CryptoError::InvalidKey(e.to_string()))?;
        Ok(format!("{salt}${}", hex::encode(hash)))
    }

    pub fn verify_password(password: &str, stored: &str) -> Result<bool, CryptoError> {
        let parts: Vec<&str> = stored.split('$').collect();
        if parts.len() != 2 {
            return Err(CryptoError::InvalidKey("Invalid hash format".into()));
        }
        let salt = parts[0];
        let expected_hash =
            hex::decode(parts[1]).map_err(|_| CryptoError::InvalidKey("Invalid hash hex".into()))?;

        let mut hash = vec![0u8; 32];
        Argon2::default()
            .hash_password_into(password.as_bytes(), salt.as_bytes(), &mut hash)
            .map_err(|e| CryptoError::InvalidKey(e.to_string()))?;

        Ok(hash == expected_hash)
    }

    pub fn hash_sha256(data: &[u8]) -> Vec<u8> {
        let mut hasher = Sha256::new();
        hasher.update(data);
        hasher.finalize().to_vec()
    }

    pub fn generate_token() -> String {
        let mut buf = vec![0u8; 32];
        OsRng.fill_bytes(&mut buf);
        hex::encode(buf)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encrypt_decrypt_roundtrip() {
        let engine = CryptoEngine::new("test-master-key-12345");
        let plaintext = b"Hello, ifinmail! This is sensitive data.";
        let encrypted = engine.encrypt(plaintext).unwrap();
        let decrypted = engine.decrypt(&encrypted).unwrap();
        assert_eq!(decrypted, plaintext);
    }

    #[test]
    fn test_encrypt_different_salts() {
        let engine = CryptoEngine::new("test-key");
        let plaintext = b"same data";
        let enc1 = engine.encrypt(plaintext).unwrap();
        let enc2 = engine.encrypt(plaintext).unwrap();
        assert_ne!(enc1.ciphertext, enc2.ciphertext);
        assert_ne!(enc1.salt, enc2.salt);
        assert_ne!(enc1.nonce, enc2.nonce);
    }

    #[test]
    fn test_password_hash_verify() {
        let password = "my_secure_password_123!";
        let stored = CryptoEngine::hash_password(password).unwrap();
        assert!(stored.contains('$'));
        assert!(CryptoEngine::verify_password(password, &stored).unwrap());
    }

    #[test]
    fn test_password_wrong() {
        let stored = CryptoEngine::hash_password("correct").unwrap();
        assert!(!CryptoEngine::verify_password("wrong", &stored).unwrap());
    }

    #[test]
    fn test_sha256() {
        let hash = CryptoEngine::hash_sha256(b"hello");
        assert_eq!(hash.len(), 32);
    }

    #[test]
    fn test_token_generation() {
        let t1 = CryptoEngine::generate_token();
        let t2 = CryptoEngine::generate_token();
        assert_ne!(t1, t2);
        assert_eq!(t1.len(), 64);
    }

    #[test]
    fn test_different_keys_fail() {
        let engine1 = CryptoEngine::new("key1");
        let engine2 = CryptoEngine::new("key2");
        let encrypted = engine1.encrypt(b"secret").unwrap();
        assert!(engine2.decrypt(&encrypted).is_err());
    }
}
