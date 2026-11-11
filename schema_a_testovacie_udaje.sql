-- MILNIK 2: schema a skutocne ulozene TESTOVACIE udaje zo skusobneho behu.
-- Import celeho suboru iba do prazdnej databazy. Migracia existujucej DB: schema.sql + seed.sql.
BEGIN;
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

-- Milnik 2. Existujuce tabulky a ich udaje zostavaju zachovane.
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE TABLE IF NOT EXISTS parkovacie_miesto (
 id SERIAL PRIMARY KEY,
 oznacenie VARCHAR(20) NOT NULL UNIQUE,
 aktivne BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS tarifa (
 id SERIAL PRIMARY KEY,
 nazov VARCHAR(100) NOT NULL UNIQUE,
 cena_za_hodinu NUMERIC(10,2) NOT NULL CHECK (cena_za_hodinu > 0),
 mena CHAR(3) NOT NULL DEFAULT 'EUR' CHECK (mena = 'EUR'),
 aktivna BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS rezervacia (
 id SERIAL PRIMARY KEY,
 poziadavka UUID NOT NULL UNIQUE,
 vozidlo_id INTEGER NOT NULL REFERENCES vozidlo(id),
 miesto_id INTEGER REFERENCES parkovacie_miesto(id),
 tarifa_id INTEGER NOT NULL REFERENCES tarifa(id),
 zaciatok TIMESTAMPTZ NOT NULL,
 koniec TIMESTAMPTZ NOT NULL,
 sadzba NUMERIC(10,2) NOT NULL CHECK (sadzba > 0),
 cena NUMERIC(10,2) NOT NULL CHECK (cena > 0),
 stav VARCHAR(20) NOT NULL CHECK (stav IN ('potvrdena','zamietnuta')),
 testovaci BOOLEAN NOT NULL DEFAULT FALSE,
 vytvorena TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CHECK (koniec > zaciatok),
 CHECK ((stav = 'potvrdena' AND miesto_id IS NOT NULL) OR
        (stav = 'zamietnuta' AND miesto_id IS NULL)),
 CHECK (cena = round(sadzba * ceil(extract(epoch FROM (koniec-zaciatok))/3600), 2)),
 EXCLUDE USING gist (miesto_id WITH =, tstzrange(zaciatok,koniec,'[)') WITH &&)
   WHERE (stav = 'potvrdena'),
 EXCLUDE USING gist (vozidlo_id WITH =, tstzrange(zaciatok,koniec,'[)') WITH &&)
   WHERE (stav = 'potvrdena')
);
CREATE TABLE IF NOT EXISTS platba (
 id SERIAL PRIMARY KEY,
 rezervacia_id INTEGER NOT NULL UNIQUE REFERENCES rezervacia(id),
 suma NUMERIC(10,2) NOT NULL CHECK (suma > 0),
 stav VARCHAR(20) NOT NULL CHECK (stav IN ('uspesna','odmietnuta')),
 metoda VARCHAR(20) NOT NULL DEFAULT 'simulacia' CHECK (metoda = 'simulacia'),
 vytvorena TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE OR REPLACE FUNCTION over_platbu() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r rezervacia; p platba;
BEGIN
 IF TG_TABLE_NAME = 'rezervacia' THEN
   SELECT * INTO r FROM rezervacia WHERE id = COALESCE(NEW.id,OLD.id);
 ELSE
   SELECT * INTO r FROM rezervacia WHERE id = COALESCE(NEW.rezervacia_id,OLD.rezervacia_id);
 END IF;
 IF r.id IS NULL THEN RETURN NULL; END IF;
 SELECT * INTO p FROM platba WHERE rezervacia_id = r.id;
 IF p.id IS NULL OR p.suma <> r.cena OR
    p.stav <> (CASE WHEN r.stav='potvrdena' THEN 'uspesna' ELSE 'odmietnuta' END) THEN
   RAISE EXCEPTION 'Rezervacia vyzaduje zodpovedajucu simulovanu platbu' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;
DROP TRIGGER IF EXISTS rezervacia_platba ON rezervacia;
CREATE CONSTRAINT TRIGGER rezervacia_platba AFTER INSERT OR UPDATE ON rezervacia
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION over_platbu();
DROP TRIGGER IF EXISTS platba_rezervacia ON platba;
CREATE CONSTRAINT TRIGGER platba_rezervacia AFTER INSERT OR UPDATE OR DELETE ON platba
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION over_platbu();
CREATE OR REPLACE FUNCTION chran_rezervaciu() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.stav='potvrdena' THEN
   RAISE EXCEPTION 'Potvrdena rezervacia je nemenne historicke potvrdenie' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS pevna_cena ON rezervacia;
CREATE TRIGGER pevna_cena BEFORE UPDATE OR DELETE ON rezervacia
 FOR EACH ROW EXECUTE FUNCTION chran_rezervaciu();
CREATE OR REPLACE FUNCTION chran_platbu() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'Zaznam simulovanej platby je nemenny' USING ERRCODE='23514';
END $$;
DROP TRIGGER IF EXISTS nemenny_vysledok_platby ON platba;
CREATE TRIGGER nemenny_vysledok_platby BEFORE UPDATE OR DELETE ON platba
 FOR EACH ROW EXECUTE FUNCTION chran_platbu();
COMMIT;

BEGIN;
SET CONSTRAINTS ALL DEFERRED;
INSERT INTO pouzivatel (id,meno,email,telefon,heslo_hash,kredit,vytvoreny) VALUES (1,'TEST – Študent','student.test@example.invalid','TEST-000','!test-account-no-login',0.00,'2026-11-11T13:29:25.994866'::timestamp);
SELECT setval(pg_get_serial_sequence('pouzivatel','id'), COALESCE((SELECT max(id) FROM pouzivatel),1), EXISTS(SELECT 1 FROM pouzivatel));
INSERT INTO vozidlo (id,pouzivatel_id,evc) VALUES (1,1,'TEST003');
INSERT INTO vozidlo (id,pouzivatel_id,evc) VALUES (2,1,'TEST001');
INSERT INTO vozidlo (id,pouzivatel_id,evc) VALUES (3,1,'TEST002');
SELECT setval(pg_get_serial_sequence('vozidlo','id'), COALESCE((SELECT max(id) FROM vozidlo),1), EXISTS(SELECT 1 FROM vozidlo));
INSERT INTO parkovacie_miesto (id,oznacenie,aktivne) VALUES (1,'TEST-A01',true);
INSERT INTO parkovacie_miesto (id,oznacenie,aktivne) VALUES (2,'TEST-A02',true);
SELECT setval(pg_get_serial_sequence('parkovacie_miesto','id'), COALESCE((SELECT max(id) FROM parkovacie_miesto),1), EXISTS(SELECT 1 FROM parkovacie_miesto));
INSERT INTO tarifa (id,nazov,cena_za_hodinu,mena,aktivna) VALUES (1,'TEST – štandardná tarifa',2.50,'EUR',true);
SELECT setval(pg_get_serial_sequence('tarifa','id'), COALESCE((SELECT max(id) FROM tarifa),1), EXISTS(SELECT 1 FROM tarifa));
INSERT INTO rezervacia (id,poziadavka,vozidlo_id,miesto_id,tarifa_id,zaciatok,koniec,sadzba,cena,stav,testovaci,vytvorena) VALUES (1,'4d38d475-900c-4be2-8154-45a176d2ef1a',1,1,1,'2026-12-11T10:00:00+01:00'::timestamptz,'2026-12-11T12:00:00+01:00'::timestamptz,2.50,5.00,'potvrdena',true,'2026-11-11T13:33:59.018201+01:00'::timestamptz);
INSERT INTO rezervacia (id,poziadavka,vozidlo_id,miesto_id,tarifa_id,zaciatok,koniec,sadzba,cena,stav,testovaci,vytvorena) VALUES (2,'77d2380b-2a5e-4d52-ae4d-768a1c7dbd35',2,NULL,1,'2026-12-11T10:00:00+01:00'::timestamptz,'2026-12-11T12:00:00+01:00'::timestamptz,2.50,5.00,'zamietnuta',true,'2026-11-11T13:33:59.484387+01:00'::timestamptz);
INSERT INTO rezervacia (id,poziadavka,vozidlo_id,miesto_id,tarifa_id,zaciatok,koniec,sadzba,cena,stav,testovaci,vytvorena) VALUES (3,'813f6d83-7b6f-4f1e-bb82-bb1ef2bbe22d',2,2,1,'2026-12-11T10:00:00+01:00'::timestamptz,'2026-12-11T12:00:00+01:00'::timestamptz,2.50,5.00,'potvrdena',true,'2026-11-11T13:33:59.922919+01:00'::timestamptz);
SELECT setval(pg_get_serial_sequence('rezervacia','id'), COALESCE((SELECT max(id) FROM rezervacia),1), EXISTS(SELECT 1 FROM rezervacia));
INSERT INTO platba (id,rezervacia_id,suma,stav,metoda,vytvorena) VALUES (1,1,5.00,'uspesna','simulacia','2026-11-11T13:33:59.018201+01:00'::timestamptz);
INSERT INTO platba (id,rezervacia_id,suma,stav,metoda,vytvorena) VALUES (2,2,5.00,'odmietnuta','simulacia','2026-11-11T13:33:59.484387+01:00'::timestamptz);
INSERT INTO platba (id,rezervacia_id,suma,stav,metoda,vytvorena) VALUES (3,3,5.00,'uspesna','simulacia','2026-11-11T13:33:59.922919+01:00'::timestamptz);
SELECT setval(pg_get_serial_sequence('platba','id'), COALESCE((SELECT max(id) FROM platba),1), EXISTS(SELECT 1 FROM platba));
COMMIT;
