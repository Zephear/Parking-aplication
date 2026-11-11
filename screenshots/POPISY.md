# Popisy skutočných snímok

1. **Cenová ponuka** – Overená dostupnosť dvoch miest a cena 5,00 € za dve hodiny pred simuláciou platby.
2. **Úspešná rezervácia** – Uložená rezervácia č. 1, vozidlo TEST003, miesto TEST-A01, pevná cena 5,00 €.
3. **Odmietnutá platba** – Zamietnutý výsledok č. 2 bez prideleného miesta a bez potvrdenej rezervácie.
4. **Plná kapacita** – Obe miesta sú obsadené; ďalšia rezervácia ani platba nevznikli.
5. **Tabuľky PostgreSQL** – Skutočné tabuľky pôvodného projektu a rozšírenia zobrazené v SQL-kliente Adminer.
6. **Uložené záznamy** – Priamy SQL SELECT dvoch úspešných rezervácií, jedného zamietnutého výsledku a troch simulovaných platieb.
7. **Verzia a obmedzenia** – PostgreSQL 16.6, PK/FK, CHECK, UNIQUE a ochrana proti prekrytiu pomocou EXCLUDE.

Zachytené 11. 11. 2026 zo skutočného behu aplikácie a SQL-klienta v Edge.
Čas testovacích rezervácií: 11. 12. 2026 od 10:00 do 12:00, Europe/Bratislava.
PNG sú neupravované. Technické podrobnosti a skutočne vykonané kontroly: OVERENIE.md v projekte.
