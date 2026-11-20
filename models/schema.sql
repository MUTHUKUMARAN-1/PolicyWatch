-- ====================================================================
-- PRIVACY POLICY AND TERMS & CONDITIONS CHANGE TRACKER (PolicyWatch)
-- Database Schema (SQLite) - Unified All-Modules Architecture
-- ====================================================================

PRAGMA foreign_keys = ON;

-- 1. Users Table
CREATE TABLE IF NOT EXISTS Users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Websites Table
CREATE TABLE IF NOT EXISTS Websites (
    website_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    website_name TEXT NOT NULL,
    website_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- 3. PrivacyPolicies Table
CREATE TABLE IF NOT EXISTS PrivacyPolicies (
    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    website_id INTEGER NOT NULL,
    policy_content TEXT NOT NULL,
    version INTEGER NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (website_id) REFERENCES Websites(website_id) ON DELETE CASCADE
);

-- 4. TermsConditions Table
CREATE TABLE IF NOT EXISTS TermsConditions (
    terms_id INTEGER PRIMARY KEY AUTOINCREMENT,
    website_id INTEGER NOT NULL,
    terms_content TEXT NOT NULL,
    version INTEGER NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (website_id) REFERENCES Websites(website_id) ON DELETE CASCADE
);

-- 5. ChangeHistory Table (Enhanced with Module 4 & Change Detection metadata)
CREATE TABLE IF NOT EXISTS ChangeHistory (
    change_id INTEGER PRIMARY KEY AUTOINCREMENT,
    website_id INTEGER NOT NULL,
    change_type TEXT NOT NULL CHECK(change_type IN ('Privacy Policy', 'Terms & Conditions')),
    old_version INTEGER,
    new_version INTEGER NOT NULL,
    change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    summary TEXT,
    category TEXT DEFAULT 'general',
    severity TEXT DEFAULT 'moderate',
    reasons TEXT,
    review_status TEXT DEFAULT 'unreviewed',
    reviewed_by TEXT,
    review_notes TEXT,
    diff_json TEXT,
    FOREIGN KEY (website_id) REFERENCES Websites(website_id) ON DELETE CASCADE
);

-- 6. Module 5: Source Freshness Table
CREATE TABLE IF NOT EXISTS m5_source_freshness (
    source_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    last_checked_at TEXT,
    last_changed_at TEXT,
    last_status TEXT NOT NULL DEFAULT 'never_checked',
    last_error TEXT,
    updated_at TEXT NOT NULL
);

-- 7. Module 5: Notifications Table
CREATE TABLE IF NOT EXISTS m5_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    website_id INTEGER,
    change_id INTEGER,
    FOREIGN KEY(source_id) REFERENCES m5_source_freshness(source_id) ON DELETE CASCADE,
    FOREIGN KEY(website_id) REFERENCES Websites(website_id) ON DELETE CASCADE,
    FOREIGN KEY(change_id) REFERENCES ChangeHistory(change_id) ON DELETE SET NULL
);

-- 8. Module 1: Scraper Snapshots Table
CREATE TABLE IF NOT EXISTS ScraperSnapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    website_id INTEGER,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    http_status INTEGER DEFAULT 200,
    content_hash TEXT,
    byte_size INTEGER DEFAULT 0,
    file_path TEXT,
    FOREIGN KEY(website_id) REFERENCES Websites(website_id) ON DELETE CASCADE
);

-- Indexes for performance and query optimization
CREATE INDEX IF NOT EXISTS idx_websites_user ON Websites(user_id);
CREATE INDEX IF NOT EXISTS idx_privacy_website ON PrivacyPolicies(website_id);
CREATE INDEX IF NOT EXISTS idx_terms_website ON TermsConditions(website_id);
CREATE INDEX IF NOT EXISTS idx_change_website ON ChangeHistory(website_id);
CREATE INDEX IF NOT EXISTS idx_change_date ON ChangeHistory(change_date);
CREATE INDEX IF NOT EXISTS idx_change_category ON ChangeHistory(category);
CREATE INDEX IF NOT EXISTS idx_change_severity ON ChangeHistory(severity);
CREATE INDEX IF NOT EXISTS idx_m5_notifications_unread ON m5_notifications(is_read, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_m5_freshness_checked ON m5_source_freshness(last_checked_at);
