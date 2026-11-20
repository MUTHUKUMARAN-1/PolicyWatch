-- ====================================================================
-- PRIVACY POLICY AND TERMS & CONDITIONS CHANGE TRACKER
-- Database Schema (SQLite)
-- ====================================================================

-- Enable Foreign Key constraint enforcement
PRAGMA foreign_keys = ON;

-- 1. Users Table
-- Stores registered user accounts with securely hashed passwords
CREATE TABLE IF NOT EXISTS Users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Websites Table
-- Stores websites tracked by users (One-to-Many: User -> Websites)
CREATE TABLE IF NOT EXISTS Websites (
    website_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    website_name TEXT NOT NULL,
    website_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);

-- 3. PrivacyPolicies Table
-- Stores versioned privacy policy documents (One-to-Many: Website -> PrivacyPolicies)
CREATE TABLE IF NOT EXISTS PrivacyPolicies (
    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    website_id INTEGER NOT NULL,
    policy_content TEXT NOT NULL,
    version INTEGER NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (website_id) REFERENCES Websites(website_id) ON DELETE CASCADE
);

-- 4. TermsConditions Table
-- Stores versioned terms and conditions documents (One-to-Many: Website -> TermsConditions)
CREATE TABLE IF NOT EXISTS TermsConditions (
    terms_id INTEGER PRIMARY KEY AUTOINCREMENT,
    website_id INTEGER NOT NULL,
    terms_content TEXT NOT NULL,
    version INTEGER NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (website_id) REFERENCES Websites(website_id) ON DELETE CASCADE
);

-- 5. ChangeHistory Table
-- Audit log of changes made to Privacy Policies and Terms & Conditions
CREATE TABLE IF NOT EXISTS ChangeHistory (
    change_id INTEGER PRIMARY KEY AUTOINCREMENT,
    website_id INTEGER NOT NULL,
    change_type TEXT NOT NULL CHECK(change_type IN ('Privacy Policy', 'Terms & Conditions')),
    old_version INTEGER,
    new_version INTEGER NOT NULL,
    change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (website_id) REFERENCES Websites(website_id) ON DELETE CASCADE
);

-- Indexes for performance and query optimization
CREATE INDEX IF NOT EXISTS idx_websites_user ON Websites(user_id);
CREATE INDEX IF NOT EXISTS idx_privacy_website ON PrivacyPolicies(website_id);
CREATE INDEX IF NOT EXISTS idx_terms_website ON TermsConditions(website_id);
CREATE INDEX IF NOT EXISTS idx_change_website ON ChangeHistory(website_id);
