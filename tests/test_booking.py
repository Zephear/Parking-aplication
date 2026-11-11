"""Integration tests. Requires a dedicated, empty TEST_DATABASE_URL database."""
import os
import re
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import psycopg2

os.environ['DATABASE_URL'] = os.environ['TEST_DATABASE_URL']
from app import app, db, init_db
from booking import cena


class BookingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True)
        init_db()
        with db() as conn, conn.cursor() as cur:
            cur.execute(Path('seed.sql').read_text(encoding='utf-8-sig'))
            cur.execute("SELECT v.id FROM vozidlo v JOIN pouzivatel p ON p.id=v.pouzivatel_id WHERE p.email='student.test@example.invalid' ORDER BY v.id")
            cls.vehicles=[r[0] for r in cur.fetchall()]
            cur.execute('SELECT id FROM tarifa ORDER BY id LIMIT 1')
            cls.tariff=cur.fetchone()[0]
        cls.base=(datetime.now(timezone.utc)+timedelta(days=60)).replace(hour=10, minute=0,second=0,microsecond=0)

    def form(self, vehicle=0, day=0, minute=0):
        start=self.base+timedelta(days=day,minutes=minute)
        # UTC to Bratislava for actual application form.
        from booking import ZONE
        return dict(vozidlo=str(self.vehicles[vehicle]),tarifa=str(self.tariff),
                    zaciatok=start.astimezone(ZONE).strftime('%Y-%m-%dT%H:%M'),
                    koniec=(start+timedelta(hours=2)).astimezone(ZONE).strftime('%Y-%m-%dT%H:%M'))

    def quote(self, client, vehicle=0, day=0, minute=0):
        client.get('/rezervacia')
        with client.session_transaction() as s: csrf=s['csrf']
        response=client.post('/rezervacia',data=dict(self.form(vehicle,day,minute),csrf=csrf))
        self.assertEqual(response.status_code,200)
        token=re.search(r'name="token" value="([^"]+)"',response.get_data(as_text=True))
        self.assertIsNotNone(token,response.get_data(as_text=True))
        return dict(token=token[1],csrf=csrf)

    def pay(self,client,q,decision='uspech'):
        return client.post('/platba',data=dict(q,rozhodnutie=decision),follow_redirects=True)

    def test_01_templates_registration(self):
        c=app.test_client()
        for route in ['/','/pouzivatelia','/rezervacia']:
            self.assertEqual(c.get(route).status_code,200)
        with c.session_transaction() as s: csrf=s['csrf']
        r=c.post('/',data=dict(csrf=csrf,meno='TEST registrácia',email=f'{uuid.uuid4()}@example.invalid',telefon='TEST',heslo='test-password-only',evc='REGTEST'),follow_redirects=True)
        self.assertIn('Registrácia úspešná',r.get_data(as_text=True))

    def test_02_success_and_idempotency(self):
        c=app.test_client(); q=self.quote(c,day=2)
        r=self.pay(c,q)
        self.assertIn('Rezervácia potvrdená',r.get_data(as_text=True))
        again=self.pay(c,q)
        self.assertEqual(r.request.path,again.request.path)
        with db() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM rezervacia r JOIN platba p ON p.rezervacia_id=r.id WHERE r.stav='potvrdena' AND p.stav='uspesna' AND r.id=%s",(int(r.request.path.split('/')[-1]),))
            self.assertEqual(cur.fetchone()[0],1)

    def test_03_decline_frees_capacity(self):
        c=app.test_client(); q=self.quote(c,day=3)
        r=self.pay(c,q,'odmietnutie')
        self.assertIn('Platba odmietnutá',r.get_data(as_text=True))
        with db() as conn, conn.cursor() as cur:
            cur.execute('SELECT stav,miesto_id FROM rezervacia WHERE id=%s',(int(r.request.path.split('/')[-1]),))
            self.assertEqual(cur.fetchone(),('zamietnuta',None))
        self.assertIn('Rezervácia potvrdená', self.pay(c,self.quote(c,day=3)).get_data(as_text=True))

    def test_04_concurrent_last_slot_and_capacity(self):
        a,b,c=app.test_client(),app.test_client(),app.test_client()
        self.pay(a,self.quote(a,0,4))
        qb,qc=self.quote(b,1,4),self.quote(c,2,4)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda x:self.pay(*x),[(b,qb),(c,qc)]))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        with db() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM rezervacia WHERE zaciatok=%s AND stav='potvrdena'",(self.base+timedelta(days=4),))
            self.assertEqual(cur.fetchone()[0],2)
        with c.session_transaction() as s: csrf=s['csrf']
        r=c.post('/rezervacia',data=dict(self.form(2,4),csrf=csrf))
        self.assertEqual(r.status_code,409)

    def test_05_frozen_quote_and_confirmed_price(self):
        c=app.test_client(); q=self.quote(c,day=5)
        try:
            with db() as conn, conn.cursor() as cur:
                cur.execute('UPDATE tarifa SET cena_za_hodinu=9 WHERE id=%s',(self.tariff,))
            r=self.pay(c,q); rid=int(r.request.path.split('/')[-1])
            with db() as conn, conn.cursor() as cur:
                cur.execute('SELECT cena,sadzba FROM rezervacia WHERE id=%s',(rid,))
                self.assertEqual(cur.fetchone(),(Decimal('5.00'),Decimal('2.50')))
            with self.assertRaises(psycopg2.errors.CheckViolation):
                with db() as conn, conn.cursor() as cur:
                    cur.execute('UPDATE rezervacia SET cena=18,sadzba=9 WHERE id=%s',(rid,))
        finally:
            with db() as conn, conn.cursor() as cur:
                cur.execute('UPDATE tarifa SET cena_za_hodinu=2.50 WHERE id=%s',(self.tariff,))

    def test_06_database_guards(self):
        c=app.test_client(); r=self.pay(c,self.quote(c,day=6)); rid=int(r.request.path.split('/')[-1])
        with self.assertRaises(psycopg2.errors.ExclusionViolation):
            with db() as conn, conn.cursor() as cur:
                cur.execute("INSERT INTO rezervacia (poziadavka,vozidlo_id,miesto_id,tarifa_id,zaciatok,koniec,sadzba,cena,stav) SELECT %s,vozidlo_id,miesto_id,tarifa_id,zaciatok,koniec,sadzba,cena,stav FROM rezervacia WHERE id=%s",(str(uuid.uuid4()),rid))
        with self.assertRaises(psycopg2.errors.CheckViolation):
            with db() as conn, conn.cursor() as cur:
                cur.execute("INSERT INTO rezervacia (poziadavka,vozidlo_id,miesto_id,tarifa_id,zaciatok,koniec,sadzba,cena,stav) SELECT %s,vozidlo_id,miesto_id,tarifa_id,zaciatok+interval '10 days',koniec+interval '10 days',sadzba,cena,stav FROM rezervacia WHERE id=%s",(str(uuid.uuid4()),rid))
        with self.assertRaises(psycopg2.errors.CheckViolation):
            with db() as conn, conn.cursor() as cur:
                cur.execute('DELETE FROM platba WHERE rezervacia_id=%s',(rid,))

    def test_07_boundary_and_vehicle_overlap(self):
        c=app.test_client(); self.pay(c,self.quote(c,day=7))
        with c.session_transaction() as s: csrf=s['csrf']
        r=c.post('/rezervacia',data=dict(self.form(0,7,30),csrf=csrf))
        self.assertNotIn('name="token"',r.get_data(as_text=True))
        self.assertIn('Rezervácia potvrdená',self.pay(c,self.quote(c,0,7,120)).get_data(as_text=True))

    def test_08_invalid_csrf_quote_and_time(self):
        c=app.test_client()
        self.assertEqual(c.post('/platba',data={}).status_code,400)
        q=self.quote(c,day=8); q['token']+='tampered'
        self.assertEqual(self.pay(c,q).status_code,400)
        from booking import miestny_cas
        for value in ['2027-03-28T02:30','2027-10-31T02:30']:
            with self.assertRaises(ValueError): miestny_cas(value)
        start=self.base
        self.assertEqual(cena(Decimal('2.50'),start,start+timedelta(minutes=61)),Decimal('5.00'))
        with self.assertRaises(ValueError): cena(Decimal('2.50'),start,start)

if __name__=='__main__': unittest.main(verbosity=2)
