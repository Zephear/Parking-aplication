# Reálne overenie – míľnik 2

Dátum: 11. 11. 2026. Jazyk aplikácie a popisov: slovenčina.

## Prostredie a postup

Reálne spustené: Windows, Python 3.12, Flask 3.0.3, psycopg2 2.9.9,
PostgreSQL **16.6** (prenosné binárne súbory), Edge cez Playwright a
SQL-klient **Adminer 6.3.0** v slovenčine cez existujúce PHP 8.0.30.
PostgreSQL počúval len na 127.0.0.1:55432, Flask na 127.0.0.1:5000,
Adminer na 127.0.0.1:8088. Použitý bol samostatný testovací klaster a databázy,
nie existujúca používateľská databáza. Balíky Python boli iba v izolovanom
virtuálnom prostredí projektu; žiadna systémová inštalácia ani služba sa nepridala.
Existujúci PostgreSQL 17 sa na testovanie nepoužil.

Prenosný PostgreSQL bol získaný od EnterpriseDB. SQL-klient bol stiahnutý z
[oficiálneho Adminer webu](https://www.adminer.org/).
Docker nebol použitý: daemon nebol dostupný. Docker build a kontajnerové spustenie
preto nie sú označené ako otestované. Príkaz `docker compose config --quiet` tiež neprešiel: dostupné Docker CLI
neposkytlo použiteľný Compose príkaz (chyba „unknown flag: --quiet“).
Konfigurácia je pripravená, ale jej validácia cez Compose nebola úspešná.

## Vykonané overenia

Všetkých **8 integračných testov prešlo** na skutočnej PostgreSQL 16.6.
Neupravovaný výstup posledného behu je v `tests/realny_vysledok.txt`.

1. GET registrácie, zoznamu a rezervácie; registrácia uloží používateľa a vozidlo.
2. Úspešná platba a rezervácia; opakované odoslanie tej istej ponuky nepridá ďalší záznam.
3. Odmietnutá platba uloží zamietnutý výsledok bez miesta; následná úspešná rezervácia je možná.
4. Dve súbežné HTTP požiadavky na posledné miesto: jeden úspech, jeden konflikt 409.
   Pri kapacite dva zostali presne dve potvrdené rezervácie; ďalšia ponuka bola odmietnutá.
5. Zmena tarify po ponuke z 2,50 na 9,00 €: rezervácia stále uložila 5,00 € za dve hodiny.
   Priamy SQL pokus zmeniť potvrdenú cenu bol zamietnutý.
6. Priame SQL prekrytie miesta bolo zamietnuté EXCLUDE constraintom; potvrdenie
   bez platby bolo zamietnuté pri commite; zmazanie platby bolo zamietnuté triggerom.
7. Prekrytie jedného vozidla sa odmietlo; nadväzujúca rezervácia s rovnakým koncom/začiatkom prešla.
8. Chýbajúci CSRF token a pozmenená cenová ponuka boli odmietnuté; nejednoznačný
   a neexistujúci lokálny čas sa odmietol; 61 minút sa účtovalo ako dve hodiny.

Navyše bol reálne importovaný celý `schema_a_testovacie_udaje.sql` do novej prázdnej
PostgreSQL databázy. Počty: 1 používateľ, 3 vozidlá, 2 miesta, 1 tarifa,
3 rezervácie a 3 platby; z rezervácií dve potvrdené a jedna zamietnutá.
V ďalšej databáze sa vytvorili pôvodné tabuľky a existujúci TEST používateľ/vozidlo.
Po migrácii zostali zachované; druhé aplikovanie schémy a seedu nevytvorilo duplikáty.

## Skutočný beh v prehliadači

Čas rezervácií: **11. 12. 2026, 10:00–12:00 Europe/Bratislava**.
Všetky údaje sú testovacie. Cena: 2 × 2,50 € = 5,00 €.

- Rezervácia 1: TEST003, TEST-A01, potvrdená, platba úspešná.
- Rezervácia 2: TEST001, miesto nepridelené, zamietnutá, platba odmietnutá.
- Rezervácia 3: TEST001, TEST-A02, potvrdená, platba úspešná.
- Po obsadení oboch miest ďalší pokus skončil hlásením „Žiadne voľné miesta“;
  nepribudla rezervácia ani platba. Priamy SELECT v Admineri vrátil presne tri páry záznamov.

## Popisy obrázkov na vloženie do Word/PDF

| Súbor | Popis obrázka |
|---|---|
| 01_cenova_ponuka.png | Obrázok 1 – Overená dostupnosť dvoch miest a cenová ponuka 5,00 € pred simuláciou platby. |
| 02_uspesna_rezervacia.png | Obrázok 2 – Úspešná testovacia rezervácia č. 1 po uložení do PostgreSQL, miesto TEST-A01 a pevná cena 5,00 €. |
| 03_odmietnuta_platba.png | Obrázok 3 – Odmietnutá simulovaná platba; potvrdená rezervácia nevznikla a miesto nebolo pridelené. |
| 04_plna_kapacita.png | Obrázok 4 – Nedostupná kapacita po obsadení oboch miest; platba ani rezervácia nevznikli. |
| 05_postgresql_tabulky.png | Obrázok 5 – Šesť skutočných tabuliek schémy public v PostgreSQL zobrazených SQL-klientom Adminer. |
| 06_postgresql_zaznamy.png | Obrázok 6 – Priamy SELECT v SQL-kliente: dve potvrdené rezervácie, jeden zamietnutý výsledok a príslušné platby. |
| 07_postgresql_obmedzenia.png | Obrázok 7 – Priamy SQL výpis verzie PostgreSQL 16.6 a obmedzení PK, FK, CHECK, UNIQUE a EXCLUDE. |

PNG vznikli priamym zachytením skutočných stránok v Edge (headless), bez kreslenia
alebo úpravy rozhrania, bez nahrádzania SQL výsledkov a bez retuše.
Snímky boli vizuálne skontrolované; neobsahujú heslá ani prístupové kľúče.
Pôvodné PNG majú plné rozlíšenie; pri vkladaní do dokumentov nepoužívajte malé náhľady.

Po dokončení boli testovací Flask, Adminer a vytvorený prenosný PostgreSQL
zastavené. Dočasná runtime zložka vrátane binárnych súborov, virtuálneho prostredia,
testovacích databáz a prístupových údajov bola odstránená. Odovzdaný projekt
obsahuje zdroje, obnoviteľný SQL export, testy a pôvodné snímky, bez runtime a tajomstiev.
