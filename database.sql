CREATE DATABASE IF NOT EXISTS docunest CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE docunest;

CREATE TABLE IF NOT EXISTS documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    confidence DECIMAL(5,2) NOT NULL,
    upload_date DATETIME NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    text_excerpt TEXT
);

-- MySQL schema for DocuNest - Auto Document Organizer

CREATE TABLE IF NOT EXISTS documents (
  id INT AUTO_INCREMENT PRIMARY KEY,
  file_name VARCHAR(255) NOT NULL,
  category VARCHAR(64) NOT NULL,
  confidence INT DEFAULT 0,
  upload_date DATETIME NOT NULL,
  file_path VARCHAR(512) NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  extracted_text LONGTEXT
);

