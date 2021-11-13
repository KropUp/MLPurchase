import time
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import pandas as pd
import yaml
import os
import sys
from tqdm import tqdm
from datetime import datetime
import psycopg2
import psycopg2.extras
import dbconfig as creds

if len(sys.argv) < 2:
    print("No config argument")
    exit()

with open('config.yaml') as f:
    global config
    config = yaml.load(f, Loader=yaml.FullLoader)

headers = {'sec-ch-ua': '" Not;A Brand";v="99", "Google Chrome";v="91", "Chromium";v="91"',
           'sec-ch-ua-mobile':'0',
           'Upgrade-Insecure-Requests': '1',
           'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

def load_purchases(chunk_num=1):
    chunk_size = config["chunk_size"]
    df = pd.read_csv(os.path.join(config["purchases_path"], config["purchases_filename"]), dtype={"purch": str})
    return df[chunk_size * (chunk_num - 1) : chunk_size * chunk_num]

df = load_purchases(chunk_num=config["chunk_num"])
purch_list = list(df.purch)
print("Count purchases = ", len(purch_list))

async def parse_logic(session, purch):
    url = "https://zakupki.gov.ru/epz/order/notice/ep44/view/supplier-results.html?regNumber=" + purch
    async with session.get(url, headers=headers) as resp:
        text = await resp.text()
        soup = BeautifulSoup(text, features="lxml")
        purchase_name = soup.find_all("span", {'class': "cardMainInfo__content"})
        if len(purchase_name) > 0:
            purchase_name = purchase_name[0].text
        else:
            purchase_name = ""
        start_price = soup.find_all("span", {'class': "cardMainInfo__content cost"})
        if len(start_price) > 0:
            try:
                start_price = int(''.join(start_price[0].text.strip().split(',')[0].split()))
            except:
                start_price = -1
        else:
            start_price = -1
        currency = "RUB"
        el = soup.find_all("div", {'class': "cardMainInfo__section col-6"})
        if len(el) > 0:
            try:
                update_dt = el[1].find("span", {"class": "cardMainInfo__content"}).text.strip()
                update_dt = datetime.strptime(update_dt, '%d.%M.%Y')
            except:
                update_dt = datetime.now()
        else:
            update_dt = datetime.now()
        #winer_list = soup.find_all('table', {'class': 'blockInfo__table tableBlock'})
        return {"regNumber": purch, "name": purchase_name, "max_price": start_price, "currency": currency, \
            "update_dt": update_dt, "code": ""}

async def main():
    start_time = time.time()
    conn_string = "host=\'"+ creds.PGHOST + "\' port="+ "5432" + " dbname=\'"+ creds.PGDATABASE +"\' user=\'" + creds.PGUSER \
    + "\' password=\'" + creds.PGPASSWORD + "\'"
    conn = psycopg2.connect(conn_string, sslmode=creds.SSLMODE)
    print("Database connected!")
    query = '''
            INSERT INTO purchases ("regNumber", "name", "max_price", "currency", "update_dt", "code")
            VALUES (%(regNumber)s, %(name)s, %(max_price)s, %(currency)s, %(update_dt)s, %(code)s);
            '''
    chunk_size = config["async_chunk_size"]
    async with aiohttp.ClientSession() as session:
        count_epochs = len(purch_list) // chunk_size + ((len(purch_list) // chunk_size) > 0)
        print("Count batches is", count_epochs)
        for epoch in tqdm(range(count_epochs)):
            try:
                print("Epoch №", epoch) if config["print"] else None
                cur = conn.cursor()
                tasks = []
                chunk = purch_list[chunk_size * epoch : chunk_size * (epoch + 1)]
                for purch in chunk:
                    tasks.append(parse_logic(session, purch))
                res = await asyncio.gather(*tasks)
                print(res) if config["print"] else None
                for item in res:
                    cur.execute(query, item)
                conn.commit()
                cur.close()
                time.sleep(config["time_sleep"])
            except:
                conn.rollback()
                cur.close()
                print(time.time(), "Sleeping")
                time.sleep(5)
                print(time.time(), "Continue")
                continue
    conn.close()

    print("All time is ", time.time() - start_time)


asyncio.run(main())