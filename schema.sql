CREATE TABLE IF NOT EXISTS pouzivatel (
    id          SERIAL PRIMARY KEY,
    meno        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) NOT NULL UNIQUE,
    telefon     VARCHAR(30)  NOT NULL,
    heslo_hash  VARCHAR(255) NOT NULL,
    kredit      NUMERIC(10,2) NOT NULL DEFAULT 0,
    vytvoreny   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vozidlo (
    id            SERIAL PRIMARY KEY,
    pouzivatel_id INTEGER NOT NULL REFERENCES pouzivatel(id) ON DELETE CASCADE,
    evc           VARCHAR(15) NOT NULL
);
