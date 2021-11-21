import dbconfig as creds
import psycopg2
from psycopg2.extras import execute_batch
import time
from datetime import datetime

def test_conn():
    conn_string = "host=\'"+ creds.PGHOST + "\' port="+ "5432" + " dbname=\'"+ creds.PGDATABASE +"\' user=\'" + creds.PGUSER \
        + "\' password=\'" + creds.PGPASSWORD + "\'"
    print("Connection string:", conn_string)
    try:
        conn = psycopg2.connect(conn_string, sslmode=creds.SSLMODE)
        print("Database connected!")
    except:
        print("Problem occured with database connetion!")

def test_insert():
    conn_string = "host=\'"+ creds.PGHOST + "\' port="+ "5432" + " dbname=\'"+ creds.PGDATABASE +"\' user=\'" + creds.PGUSER \
        + "\' password=\'" + creds.PGPASSWORD + "\'"
    conn = psycopg2.connect(conn_string, sslmode=creds.SSLMODE)
    cur = conn.cursor()
    purchase_query = '''
            INSERT INTO {} ("regNumber", "name", "max_price", "currency", "update_dt", "code")
            VALUES (%(regNumber)s, %(name)s, %(max_price)s, %(currency)s, %(update_dt)s, %(code)s);
            '''.format("public.eis_purchases_i")
    params = [
        {"regNumber": "1", "name": "1", "max_price": 1, "currency": "1", "update_dt": datetime.now(), "code": ""},
        {"regNumber": "2", "name": "1", "max_price": 1, "currency": "1", "update_dt": datetime.now(), "code": ""},
        {"regNumber": "3", "name": "1", "max_price": 1, "currency": "1", "update_dt": datetime.now(), "code": ""}
    ]
    execute_batch(cur, purchase_query, params)
    conn.commit()
    cur.close()
    conn.close()
    

if __name__ == "__main__":
    test_conn()
    test_insert()