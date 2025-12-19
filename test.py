--
-- Файл сгенерирован с помощью SQLiteStudio v3.3.3 в Чт дек 18 15:12:41 2025
--
-- Использованная кодировка текста: System
--
PRAGMA foreign_keys = off;
BEGIN TRANSACTION;

-- Таблица: image_annotations
CREATE TABLE image_annotations (
	id INTEGER NOT NULL, 
	filename VARCHAR(200) NOT NULL, 
	annotation_file VARCHAR(200), 
	format_type VARCHAR(10), 
	labels TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id)
);

-- Таблица: questions
CREATE TABLE questions (
	id INTEGER NOT NULL, 
	question_text TEXT NOT NULL, 
	question_type VARCHAR(20), 
	correct_answer TEXT, 
	image_annotation_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(image_annotation_id) REFERENCES image_annotations (id)
);

-- Таблица: test_results
CREATE TABLE test_results (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	score FLOAT NOT NULL, 
	answers_json TEXT, 
	metrics_json TEXT, 
	started_at DATETIME, 
	completed_at DATETIME, 
	duration_seconds INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

-- Таблица: test_topics
CREATE TABLE test_topics (
	id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

-- Таблица: tests
CREATE TABLE tests (
	id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	description TEXT, 
	topic_id INTEGER, 
	creator_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(topic_id) REFERENCES test_topics (id), 
	FOREIGN KEY(creator_id) REFERENCES users (id)
);

-- Таблица: users
CREATE TABLE users (
	id INTEGER NOT NULL, 
	username VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(120) NOT NULL, 
	role VARCHAR(20), 
	language VARCHAR(5), 
	theme VARCHAR(50), 
	first_name VARCHAR(100), 
	last_name VARCHAR(100), 
	middle_name VARCHAR(100), 
	group_number VARCHAR(50), 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (username)
);

COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
