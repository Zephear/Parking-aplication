-- VYHRADNE TESTOVACIE UDAJE. Bez realnych osobnych a bankovych udajov.
-- Opakovatelne, bez mazania existujucich udajov.
INSERT INTO pouzivatel (meno,email,telefon,heslo_hash)
VALUES ('TEST – Študent','student.test@example.invalid','TEST-000','!test-account-no-login')
ON CONFLICT (email) DO NOTHING;
INSERT INTO vozidlo (pouzivatel_id,evc)
SELECT p.id, x.evc FROM pouzivatel p CROSS JOIN
 (VALUES ('TEST001'),('TEST002'),('TEST003')) x(evc)
WHERE p.email='student.test@example.invalid'
 AND NOT EXISTS (SELECT 1 FROM vozidlo v WHERE v.pouzivatel_id=p.id AND v.evc=x.evc);
INSERT INTO parkovacie_miesto (oznacenie) VALUES ('TEST-A01'),('TEST-A02')
ON CONFLICT (oznacenie) DO NOTHING;
INSERT INTO tarifa (nazov,cena_za_hodinu) VALUES ('TEST – štandardná tarifa',2.50)
ON CONFLICT (nazov) DO NOTHING;
