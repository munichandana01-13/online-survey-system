CREATE DATABASE surveydb;

USE surveydb;

CREATE TABLE users(
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(100),
    email VARCHAR(100),
    password VARCHAR(255)
);

CREATE TABLE surveys(
    id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(200),
    description TEXT,
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE questions(
    id INT PRIMARY KEY AUTO_INCREMENT,
    survey_id INT,
    question TEXT,
    question_type VARCHAR(50)
);

CREATE TABLE responses(
    id INT PRIMARY KEY AUTO_INCREMENT,
    survey_id INT,
    question_id INT,
    answer TEXT
);