-- ============================================
-- MySQL Schema for AI Avatar Receptionist
-- Database: myapp
-- ============================================

-- Visitor table: stores all recognized visitors
CREATE TABLE IF NOT EXISTS visitor (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) DEFAULT NULL,
    phone VARCHAR(50) DEFAULT NULL,
    company VARCHAR(255) DEFAULT NULL,
    consent_status VARCHAR(20) DEFAULT 'granted',
    face_embedding JSON DEFAULT NULL,
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    visit_count INT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_visitor_name (name),
    INDEX idx_visitor_last_seen (last_seen)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Visits table: tracks each visit instance
CREATE TABLE IF NOT EXISTS visits (
    id INT AUTO_INCREMENT PRIMARY KEY,
    visitor_id INT NOT NULL,
    arrival_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    departure_time DATETIME DEFAULT NULL,
    purpose TEXT DEFAULT NULL,
    status VARCHAR(20) DEFAULT 'arrived',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_visits_visitor (visitor_id),
    INDEX idx_visits_arrival (arrival_time),
    CONSTRAINT fk_visits_visitor FOREIGN KEY (visitor_id) REFERENCES visitor(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Conversations table: stores conversation messages
CREATE TABLE IF NOT EXISTS conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    visitor_id INT NOT NULL,
    role VARCHAR(20) NOT NULL COMMENT 'user, assistant, system',
    message TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_conv_visitor (visitor_id),
    INDEX idx_conv_timestamp (timestamp),
    CONSTRAINT fk_conv_visitor FOREIGN KEY (visitor_id) REFERENCES visitor(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
