"""Rezervacie: cela simulacia platby a pridelenie miesta v jednej transakcii."""
import math
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import abort, redirect, render_template, request, session, url_for
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

ZONE = ZoneInfo('Europe/Bratislava')


def cena(sadzba, zaciatok, koniec):
    sekundy = (koniec - zaciatok).total_seconds()
    if sekundy <= 0 or sekundy > 31 * 86400:
        raise ValueError('Rezervácia musí trvať viac ako 0 hodín a najviac 31 dní.')
    return (sadzba * Decimal(math.ceil(sekundy / 3600))).quantize(Decimal('0.01'))


def miestny_cas(text):
    local = datetime.fromisoformat(text)
    if local.tzinfo is not None:
        raise ValueError('Použite miestny čas bez časového pásma.')
    aware = local.replace(tzinfo=ZONE)
    if aware.astimezone(timezone.utc).astimezone(ZONE).replace(tzinfo=None) != local:
        raise ValueError('Tento čas neexistuje pre prechod na letný čas.')
    if aware.utcoffset() != local.replace(tzinfo=ZONE, fold=1).utcoffset():
        raise ValueError('Nejednoznačný čas pri zmene času. Zvoľte iný čas.')
    return aware.astimezone(timezone.utc)


def install(app, db):
    def signer():
        return URLSafeTimedSerializer(app.secret_key, salt='rezervacia-v1')

    @app.before_request
    def csrf():
        session.setdefault('csrf', secrets.token_urlsafe(32))
        if request.method == 'POST' and not secrets.compare_digest(
            session['csrf'], request.form.get('csrf', '')
        ):
            abort(400, 'Neplatný formulár. Obnovte stránku.')

    @app.template_filter('skcas')
    def skcas(value):
        return value.astimezone(ZONE).strftime('%d.%m.%Y %H:%M')

    def result(title, message, status=200, row=None):
        return render_template('vysledok.html', title=title, message=message, row=row), status

    @app.route('/rezervacia', methods=['GET', 'POST'])
    def rezervacia():
        with db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT v.id,v.evc,p.meno FROM vozidlo v JOIN pouzivatel p ON p.id=v.pouzivatel_id ORDER BY v.id')
            vozidla = cur.fetchall()
            cur.execute('SELECT * FROM tarifa WHERE aktivna ORDER BY id')
            tarify = cur.fetchall()
            error = None
            if request.method == 'POST':
                try:
                    vid, tid = int(request.form['vozidlo']), int(request.form['tarifa'])
                    start, end = miestny_cas(request.form['zaciatok']), miestny_cas(request.form['koniec'])
                    if start <= datetime.now(timezone.utc):
                        raise ValueError('Začiatok musí byť v budúcnosti.')
                    tariff = next((t for t in tarify if t['id'] == tid), None)
                    vehicle = next((v for v in vozidla if v['id'] == vid), None)
                    if not tariff or not vehicle:
                        raise ValueError('Vyberte platné vozidlo a tarifu.')
                    amount = cena(tariff['cena_za_hodinu'], start, end)
                    cur.execute("SELECT count(*) AS n FROM parkovacie_miesto m WHERE aktivne AND NOT EXISTS (SELECT 1 FROM rezervacia r WHERE r.miesto_id=m.id AND r.stav='potvrdena' AND tstzrange(r.zaciatok,r.koniec,'[)') && tstzrange(%s,%s,'[)'))", (start,end))
                    free = cur.fetchone()['n']
                    if not free:
                        return result('Žiadne voľné miesta', 'Vo zvolenom čase nie je voľné parkovacie miesto. Platba sa nevykonala a rezervácia nevznikla.', 409)
                    cur.execute("SELECT 1 FROM rezervacia WHERE vozidlo_id=%s AND stav='potvrdena' AND tstzrange(zaciatok,koniec,'[)') && tstzrange(%s,%s,'[)')", (vid,start,end))
                    if cur.fetchone():
                        raise ValueError('Vozidlo už má rezerváciu v tomto čase.')
                    quote = dict(vozidlo=vid, tarifa=tid, zaciatok=start.isoformat(), koniec=end.isoformat(), sadzba=str(tariff['cena_za_hodinu']), cena=str(amount), poziadavka=str(uuid.uuid4()), csrf=session['csrf'])
                    token = signer().dumps(quote)
                    return render_template('platba.html', token=token, amount=amount, rate=tariff['cena_za_hodinu'], vehicle=vehicle, start=start, end=end, free=free)
                except (ValueError, KeyError, StopIteration):
                    error = 'Skontrolujte vozidlo, tarifu a čas. Čas musí byť jednoznačný, v budúcnosti a trvanie najviac 31 dní.'
            return render_template('rezervacia.html', vozidla=vozidla, tarify=tarify, error=error)

    @app.post('/platba')
    def platba():
        try:
            q = signer().loads(request.form.get('token',''), max_age=900)
            if q['csrf'] != session['csrf']:
                raise BadSignature('session')
        except (BadSignature, SignatureExpired, KeyError):
            return result('Ponuka vypršala', 'Vytvorte novú cenovú ponuku. Platba sa nevykonala.', 400)
        decision = request.form.get('rozhodnutie')
        if decision not in ('uspech','odmietnutie'):
            abort(400)
        start, end = datetime.fromisoformat(q['zaciatok']), datetime.fromisoformat(q['koniec'])
        if start <= datetime.now(timezone.utc):
            return result('Neplatný čas', 'Začiatok už uplynul. Vytvorte novú ponuku.', 400)
        try:
            with db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Serialize this short local simulated transaction; no network payment under lock.
                cur.execute('SELECT pg_advisory_xact_lock(7624102)')
                cur.execute('SELECT id FROM rezervacia WHERE poziadavka=%s', (q['poziadavka'],))
                previous = cur.fetchone()
                if previous:
                    return redirect(url_for('potvrdenie', rid=previous['id']))
                cur.execute("SELECT m.id FROM parkovacie_miesto m WHERE aktivne AND NOT EXISTS (SELECT 1 FROM rezervacia r WHERE r.miesto_id=m.id AND r.stav='potvrdena' AND tstzrange(r.zaciatok,r.koniec,'[)') && tstzrange(%s,%s,'[)')) ORDER BY m.id LIMIT 1 FOR UPDATE", (start,end))
                slot = cur.fetchone()
                if not slot:
                    return result('Žiadne voľné miesta', 'Kapacita sa medzičasom vyčerpala. Platba sa nevykonala a rezervácia nevznikla.', 409)
                cur.execute('SELECT id FROM vozidlo WHERE id=%s FOR UPDATE', (q['vozidlo'],))
                if not cur.fetchone():
                    abort(400)
                cur.execute("SELECT 1 FROM rezervacia WHERE vozidlo_id=%s AND stav='potvrdena' AND tstzrange(zaciatok,koniec,'[)') && tstzrange(%s,%s,'[)')", (q['vozidlo'],start,end))
                if cur.fetchone():
                    return result('Vozidlo už má rezerváciu', 'Prekrytie času nie je povolené. Platba sa nevykonala.', 409)
                success = decision == 'uspech'
                cur.execute("INSERT INTO rezervacia (poziadavka,vozidlo_id,miesto_id,tarifa_id,zaciatok,koniec,sadzba,cena,stav,testovaci) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE) RETURNING id", (q['poziadavka'],q['vozidlo'],slot['id'] if success else None,q['tarifa'],start,end,q['sadzba'],q['cena'],'potvrdena' if success else 'zamietnuta'))
                rid = cur.fetchone()['id']
                cur.execute('INSERT INTO platba (rezervacia_id,suma,stav) VALUES (%s,%s,%s)', (rid,q['cena'],'uspesna' if success else 'odmietnuta'))
            return redirect(url_for('potvrdenie', rid=rid))
        except (psycopg2.errors.ExclusionViolation, psycopg2.errors.ForeignKeyViolation):
            return result('Rezervácia sa nepodarila', 'Dostupnosť sa zmenila. Platba ani potvrdená rezervácia neboli uložené.', 409)

    @app.get('/rezervacia/<int:rid>')
    def potvrdenie(rid):
        with db() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT r.*,v.evc,m.oznacenie,p.stav AS platba_stav FROM rezervacia r JOIN vozidlo v ON v.id=r.vozidlo_id LEFT JOIN parkovacie_miesto m ON m.id=r.miesto_id JOIN platba p ON p.rezervacia_id=r.id WHERE r.id=%s', (rid,))
            row = cur.fetchone()
        if not row:
            abort(404)
        success = row['stav'] == 'potvrdena'
        return result('Rezervácia potvrdená' if success else 'Platba odmietnutá', 'Simulovaná platba bola úspešná. Cena rezervácie je pevne uložená.' if success else 'Simulovaná platba bola odmietnutá. Potvrdená rezervácia nevznikla a miesto zostáva voľné.', row=row)
