-- ============================================
-- Migration script for existing MySQL database
-- Run this if your tables already exist but need updates
-- Usage: mysql -u appuser -p myapp < migrate.sql
-- ============================================

-- Add face_embedding column to visitor table (if not exists)
-- MySQL doesn't support IF NOT EXISTS for ALTER TABLE, so we use a procedure
DELIMITER //
CREATE PROCEDURE AddFaceEmbeddingColumn()
BEGIN
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'myapp' 
        AND TABLE_NAME = 'visitor' 
        AND COLUMN_NAME = 'face_embedding'
    ) THEN
        ALTER TABLE visitor ADD COLUMN face_embedding JSON DEFAULT NULL;
        SELECT 'Added face_embedding column' AS result;
    ELSE
        SELECT 'face_embedding column already exists' AS result;
    END IF;
END //
DELIMITER ;

CALL AddFaceEmbeddingColumn();
DROP PROCEDURE AddFaceEmbeddingColumn;

-- Add any missing columns to visitor table
DELIMITER //
CREATE PROCEDURE EnsureVisitorColumns()
BEGIN
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'myapp' AND TABLE_NAME = 'visitor' AND COLUMN_NAME = 'email'
    ) THEN
        ALTER TABLE visitor ADD COLUMN email VARCHAR(255) DEFAULT NULL;
    END IF;
    
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'myapp' AND TABLE_NAME = 'visitor' AND COLUMN_NAME = 'phone'
    ) THEN
        ALTER TABLE visitor ADD COLUMN phone VARCHAR(50) DEFAULT NULL;
    END IF;
    
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'myapp' AND TABLE_NAME = 'visitor' AND COLUMN_NAME = 'company'
    ) THEN
        ALTER TABLE visitor ADD COLUMN company VARCHAR(255) DEFAULT NULL;
    END IF;
    
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'myapp' AND TABLE_NAME = 'visitor' AND COLUMN_NAME = 'consent_status'
    ) THEN
        ALTER TABLE visitor ADD COLUMN consent_status VARCHAR(20) DEFAULT 'granted';
    END IF;
    
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'myapp' AND TABLE_NAME = 'visitor' AND COLUMN_NAME = 'first_seen'
    ) THEN
        ALTER TABLE visitor ADD COLUMN first_seen DATETIME DEFAULT CURRENT_TIMESTAMP;
    END IF;
    
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'myapp' AND TABLE_NAME = 'visitor' AND COLUMN_NAME = 'last_seen'
    ) THEN
        ALTER TABLE visitor ADD COLUMN last_seen DATETIME DEFAULT CURRENT_TIMESTAMP;
    END IF;
    
    IF NOT EXISTS (
        SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'myapp' AND TABLE_NAME = 'visitor' AND COLUMN_NAME = 'visit_count'
    ) THEN
        ALTER TABLE visitor ADD COLUMN visit_count INT DEFAULT 1;
    END IF;
    
    SELECT 'Visitor table columns ensured' AS result;
END //
DELIMITER ;

CALL EnsureVisitorColumns();
DROP PROCEDURE EnsureVisitorColumns;
