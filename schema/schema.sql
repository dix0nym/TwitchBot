CREATE TABLE song (
	id VARCHAR NOT NULL PRIMARY KEY,
	title VARCHAR(255) NOT NULL,
	url VARCHAR(255) NOT NULL,
	duration INTEGER NOT NULL,
	upload_date VARCHAR(8) NOT NULL,
	channel VARCHAR(100) NOT NULL,
	thumbnail VARCHAR(255) NOT NULL
);

CREATE TABLE user (
	id INTEGER NOT NULL PRIMARY KEY,
	name VARCHAR(255) NOT NULL,
	display_name VARCHAR(255) NOT NULL,
	created_at DATETIME NOT NULL
);

CREATE TABLE request (
	id INTEGER NOT NULL PRIMARY KEY,
	timestamp DATETIME NOT NULL,
	user_id INTEGER NOT NULL,
	song_id VARCHAR NOT NULL,
	FOREIGN KEY (user_id) REFERENCES user(id),
	FOREIGN KEY (song_id) REFERENCES song(id)
);