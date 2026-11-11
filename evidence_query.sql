SELECT r.id AS rezervacia, v.evc AS vozidlo, m.oznacenie AS miesto,
 to_char(r.zaciatok AT TIME ZONE 'Europe/Bratislava','DD.MM.YYYY HH24:MI') AS od,
 to_char(r.koniec AT TIME ZONE 'Europe/Bratislava','DD.MM.YYYY HH24:MI') AS do,
 r.cena AS cena_eur, r.stav AS rezervacia_stav, p.stav AS platba_stav,
 r.testovaci AS test
FROM rezervacia r
JOIN vozidlo v ON v.id=r.vozidlo_id
LEFT JOIN parkovacie_miesto m ON m.id=r.miesto_id
JOIN platba p ON p.rezervacia_id=r.id
ORDER BY r.id;
