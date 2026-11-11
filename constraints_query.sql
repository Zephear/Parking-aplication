SELECT current_setting('server_version') AS verzia_postgresql;
SELECT t.relname AS tabulka, c.contype AS typ, c.conname AS obmedzenie,
 pg_get_constraintdef(c.oid) AS definicia
FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
JOIN pg_namespace n ON n.oid=t.relnamespace
WHERE n.nspname='public' AND t.relname IN
 ('pouzivatel','vozidlo','parkovacie_miesto','tarifa','rezervacia','platba')
ORDER BY t.relname,c.contype,c.conname;
