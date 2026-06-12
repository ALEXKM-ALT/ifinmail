use std::collections::HashMap;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyConfig {
    /// Max sends per minute per user
    pub max_sends_per_minute: u32,
    /// Max recipients per hour per user
    pub max_recipients_per_hour: u32,
    /// Spam score threshold for rejection (0-100)
    pub spam_reject_threshold: f64,
    /// Greylist threshold
    pub greylist_threshold: f64,
    /// Trust score required for increased limits
    pub trust_threshold_high: f64,
    /// Trust score for standard limits
    pub trust_threshold_standard: f64,
    /// Whether DKIM is required for inbound
    pub require_dkim: bool,
    /// Whether SPF is required for inbound
    pub require_spf: bool,
}

impl Default for PolicyConfig {
    fn default() -> Self {
        Self {
            max_sends_per_minute: 30,
            max_recipients_per_hour: 300,
            spam_reject_threshold: 8.0,
            greylist_threshold: 4.0,
            trust_threshold_high: 80.0,
            trust_threshold_standard: 40.0,
            require_dkim: false,
            require_spf: false,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum PolicyAction {
    Allow,
    Quarantine,
    Reject(String),
    Greylist,
    Flag,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyResult {
    pub action: PolicyAction,
    pub score: f64,
    pub reasons: Vec<String>,
    pub details: HashMap<String, f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserReputation {
    pub user_id: String,
    pub trust_score: f64,
    pub total_sent: u64,
    pub total_bounces: u64,
    pub total_spam_complaints: u64,
    pub last_seen: Option<DateTime<Utc>>,
    pub age_days: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SendingLimit {
    pub user_id: String,
    pub sent_last_minute: u32,
    pub sent_last_hour: u32,
    pub recipients_last_hour: u32,
    pub reset_at: DateTime<Utc>,
}

pub struct PolicyEngine {
    config: PolicyConfig,
}

impl PolicyEngine {
    pub fn new(config: PolicyConfig) -> Self {
        Self { config }
    }

    pub fn evaluate_send(&self, limit: &SendingLimit, reputation: &UserReputation) -> PolicyResult {
        let mut score: f64 = 0.0;
        let mut reasons = Vec::new();
        let mut details = HashMap::new();

        if limit.sent_last_minute >= self.config.max_sends_per_minute {
            score += 20.0;
            reasons.push("Rate limit exceeded (per-minute)".into());
        }

        if limit.recipients_last_hour >= self.config.max_recipients_per_hour {
            score += 15.0;
            reasons.push("Recipient limit exceeded (per-hour)".into());
        }

        details.insert("sent_1m".into(), limit.sent_last_minute as f64);
        details.insert("recipients_1h".into(), limit.recipients_last_hour as f64);
        details.insert("trust_score".into(), reputation.trust_score);
        details.insert("bounce_rate".into(), reputation.bounce_rate());
        details.insert("complaint_rate".into(), reputation.complaint_rate());

        if reputation.bounce_rate() > 0.1 {
            score += 10.0;
            reasons.push(format!(
                "High bounce rate: {:.1}%",
                reputation.bounce_rate() * 100.0
            ));
        }

        if reputation.complaint_rate() > 0.01 {
            score += 20.0;
            reasons.push(format!(
                "High complaint rate: {:.1}%",
                reputation.complaint_rate() * 100.0
            ));
        }

        let action = if score >= 20.0 {
            PolicyAction::Reject("Sending blocked by policy".into())
        } else if score >= 10.0 {
            PolicyAction::Quarantine
        } else {
            PolicyAction::Allow
        };

        PolicyResult {
            action,
            score,
            reasons,
            details,
        }
    }

    pub fn evaluate_inbound(
        &self,
        spam_score: f64,
        has_dkim: bool,
        has_spf: bool,
        reputation: &UserReputation,
    ) -> PolicyResult {
        let mut score = spam_score;
        let mut reasons = Vec::new();
        let mut details = HashMap::new();

        details.insert("spam_score".into(), spam_score);
        details.insert("has_dkim".into(), if has_dkim { 1.0 } else { 0.0 });
        details.insert("has_spf".into(), if has_spf { 1.0 } else { 0.0 });

        if self.config.require_dkim && !has_dkim {
            score += 3.0;
            reasons.push("Missing DKIM signature".into());
        }

        if self.config.require_spf && !has_spf {
            score += 2.0;
            reasons.push("Missing SPF check".into());
        }

        if reputation.trust_score < self.config.trust_threshold_standard {
            score += 2.0;
            reasons.push("Low sender trust score".into());
        }

        let action = if score >= self.config.spam_reject_threshold {
            PolicyAction::Reject("Classified as spam".into())
        } else if score >= self.config.greylist_threshold {
            PolicyAction::Greylist
        } else {
            PolicyAction::Allow
        };

        PolicyResult {
            action,
            score,
            reasons,
            details,
        }
    }

    pub fn compute_trust_score(&self, reputation: &UserReputation) -> f64 {
        let mut score: f64 = 50.0;

        // Account age bonus: +10 for every 30 days (max +30)
        score += (reputation.age_days / 30.0).min(3.0) * 10.0;

        // Good sending behavior
        if reputation.total_sent > 0 {
            let ratio = reputation.total_bounces as f64 / reputation.total_sent as f64;
            let bounce_penalty = (ratio * 100.0).min(40.0);
            score -= bounce_penalty;

            let complaint_ratio =
                reputation.total_spam_complaints as f64 / reputation.total_sent as f64;
            let complaint_penalty = (complaint_ratio * 200.0).min(30.0);
            score -= complaint_penalty;
        }

        // Volume bonus
        if reputation.total_sent > 1000 {
            score += 5.0;
        }
        if reputation.total_sent > 10000 {
            score += 5.0;
        }

        score.clamp(0.0, 100.0)
    }

    pub fn allowed_send_rate(&self, trust_score: f64) -> u32 {
        if trust_score >= self.config.trust_threshold_high {
            self.config.max_sends_per_minute * 2
        } else if trust_score >= self.config.trust_threshold_standard {
            self.config.max_sends_per_minute
        } else {
            self.config.max_sends_per_minute / 2
        }
    }
}

impl UserReputation {
    pub fn new(user_id: &str) -> Self {
        Self {
            user_id: user_id.to_string(),
            trust_score: 50.0,
            total_sent: 0,
            total_bounces: 0,
            total_spam_complaints: 0,
            last_seen: None,
            age_days: 0.0,
        }
    }

    pub fn bounce_rate(&self) -> f64 {
        if self.total_sent == 0 {
            return 0.0;
        }
        self.total_bounces as f64 / self.total_sent as f64
    }

    pub fn complaint_rate(&self) -> f64 {
        if self.total_sent == 0 {
            return 0.0;
        }
        self.total_spam_complaints as f64 / self.total_sent as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn default_reputation(user_id: &str) -> UserReputation {
        UserReputation::new(user_id)
    }

    #[test]
    fn test_evaluate_send_allowed() {
        let engine = PolicyEngine::new(PolicyConfig::default());
        let limit = SendingLimit {
            user_id: "user-1".into(),
            sent_last_minute: 5,
            sent_last_hour: 50,
            recipients_last_hour: 50,
            reset_at: Utc::now(),
        };
        let rep = default_reputation("user-1");
        let result = engine.evaluate_send(&limit, &rep);
        assert_eq!(result.action, PolicyAction::Allow);
    }

    #[test]
    fn test_evaluate_send_rate_limited() {
        let engine = PolicyEngine::new(PolicyConfig::default());
        let limit = SendingLimit {
            user_id: "user-1".into(),
            sent_last_minute: 40,
            sent_last_hour: 300,
            recipients_last_hour: 400,
            reset_at: Utc::now(),
        };
        let rep = default_reputation("user-1");
        let result = engine.evaluate_send(&limit, &rep);
        assert_eq!(result.action, PolicyAction::Reject("Sending blocked by policy".into()));
        assert!(result.score >= 20.0);
    }

    #[test]
    fn test_evaluate_send_quarantine() {
        let engine = PolicyEngine::new(PolicyConfig::default());
        let limit = SendingLimit {
            user_id: "user-1".into(),
            sent_last_minute: 30,
            sent_last_hour: 200,
            recipients_last_hour: 300,
            reset_at: Utc::now(),
        };
        let mut rep = default_reputation("user-1");
        rep.total_bounces = 200;
        rep.total_sent = 1000;
        let result = engine.evaluate_send(&limit, &rep);
        assert_eq!(result.action, PolicyAction::Quarantine);
    }

    #[test]
    fn test_evaluate_inbound_allow() {
        let engine = PolicyEngine::new(PolicyConfig::default());
        let rep = default_reputation("sender");
        let result = engine.evaluate_inbound(1.5, true, true, &rep);
        assert_eq!(result.action, PolicyAction::Allow);
    }

    #[test]
    fn test_compute_trust_score_new() {
        let rep = UserReputation::new("user-1");
        let score = PolicyEngine::new(PolicyConfig::default()).compute_trust_score(&rep);
        assert!((score - 50.0).abs() < 0.01);
    }

    #[test]
    fn test_compute_trust_score_established() {
        let rep = UserReputation {
            user_id: "user-1".into(),
            trust_score: 50.0,
            total_sent: 5000,
            total_bounces: 50,
            total_spam_complaints: 5,
            last_seen: None,
            age_days: 90.0,
        };
        let score = PolicyEngine::new(PolicyConfig::default()).compute_trust_score(&rep);
        assert!(score > 0.0 && score <= 100.0);
    }

    #[test]
    fn test_allowed_send_rate() {
        let engine = PolicyEngine::new(PolicyConfig::default());
        assert_eq!(engine.allowed_send_rate(20.0), 15);
        assert_eq!(engine.allowed_send_rate(50.0), 30);
        assert_eq!(engine.allowed_send_rate(90.0), 60);
    }

    #[test]
    fn test_bounce_rate() {
        let mut rep = UserReputation::new("user-1");
        assert!((rep.bounce_rate() - 0.0).abs() < f64::EPSILON);
        rep.total_sent = 100;
        rep.total_bounces = 5;
        assert!((rep.bounce_rate() - 0.05).abs() < f64::EPSILON);
    }

    #[test]
    fn test_evaluate_inbound_reject() {
        let engine = PolicyEngine::new(PolicyConfig::default());
        let rep = default_reputation("spammer");
        let result = engine.evaluate_inbound(9.0, false, false, &rep);
        assert_eq!(result.action, PolicyAction::Reject("Classified as spam".into()));
    }

    #[test]
    fn test_evaluate_inbound_greylist() {
        let engine = PolicyEngine::new(PolicyConfig::default());
        let rep = default_reputation("unknown");
        let result = engine.evaluate_inbound(5.0, false, false, &rep);
        assert_eq!(result.action, PolicyAction::Greylist);
    }
}
