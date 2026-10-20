-- CyberSafe AI MySQL schema
-- Run: mysql -u root -p < database/schema.sql
CREATE DATABASE IF NOT EXISTS cybersafe_ai
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE cybersafe_ai;

CREATE TABLE IF NOT EXISTS users (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(150) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_sessions (
  chat_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  chat_title VARCHAR(200) NOT NULL DEFAULT 'New Chat',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_chat_user (user_id),
  CONSTRAINT fk_chat_sessions_user FOREIGN KEY (user_id)
    REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_messages (
  message_id INT AUTO_INCREMENT PRIMARY KEY,
  chat_id INT NOT NULL,
  sender ENUM('user', 'bot') NOT NULL,
  message TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_message_chat (chat_id),
  CONSTRAINT fk_chat_messages_session FOREIGN KEY (chat_id)
    REFERENCES chat_sessions(chat_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
