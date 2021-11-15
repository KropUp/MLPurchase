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
import pickle

if len(sys.argv) < 2:
    print("No config argument")
    exit()

with open('config.yaml') as f:
    global config
    config = yaml.load(f, Loader=yaml.FullLoader)

unique_inns = set()
if os.path.exists(config["unique_inns_filename"]):
    with open(config["unique_inns_filename"], 'rb') as handle:
        unique_inns = pickle.load(handle)

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

async def extract_info_from_contract(session, contract_url):
    reestrNumber = contract_url.split("reestrNumber=")[1]
    contract_url = 'https://zakupki.gov.ru' + contract_url
    async with session.get(contract_url, headers=headers) as resp:
            contract_page_text = await resp.text()
            #contract_page_text = contract_page_text.decode('utf-8')
            soup = BeautifulSoup(contract_page_text, features="lxml")
            info_dict = {"reestrNumber": reestrNumber, "inn": "","company_name": "", "phone": "", "address": "", "email": "", "price": -1}
            # Find winer info
            info = soup.find_all("tbody", {'class': "tableBlock__body"})
            if len(info) == 0:
                return info_dict
            else:
                info = info[0]
            count_headers = len(soup.find_all("th", {"class": "tableBlock__col tableBlock__col_header"}))
            for i in range(len(info.find_all("td"))):
                if i == 0:
                    name = info.find_all("td")[i].text.split('\n')
                    info_dict["company_name"] = name[1].strip() \
                        if len(name) > 1 else ""
                if i == 2:
                    info_dict["address"] = info.find_all("td")[i].text.strip()
                if i == count_headers - 2:
                    phone = info.find_all("td")[i].text.strip().split('\n')
                    info_dict["phone"] = phone[0] if len(phone) > 0 else ""
                    email = info.find_all("td")[i].text.strip().split('\n')
                    info_dict["email"] = email[1].strip() if len(email) > 1 else ""

            # Extract inn info
            spans = soup.find_all('span')
            ind_cur = -1
            for span in spans:
                if span.text == 'ИНН:': 
                    ind_cur = spans.index(span) + 1
                    break
            if ind_cur == -1:
                return 
            else:
                info_dict["inn"] = spans[ind_cur].text

            try:
                price = soup.find_all("span", {"class": "cardMainInfo__content cost"})
                price = int(''.join(price[0].text.strip().split(',')[0].split()))
            except:
                price = -1
            info_dict["price"] = price

            return info_dict

async def parse_logic(session, purch):
    url = "https://zakupki.gov.ru/epz/order/notice/ep44/view/supplier-results.html?regNumber=" + purch
    async with session.get(url, headers=headers) as resp:
        text = await resp.text()
        soup = BeautifulSoup(text, features="lxml")
        resp_dict = {"regNumber": purch, "name": "", "max_price": -1, "currency": "", \
            "update_dt": datetime.now(), "code": ""}
        reestr_header = soup.find_all("th", {"class": "tableBlock__col tableBlock__col_header"}, text="Номер реестровой записи")
        purchase_name = soup.find_all("span", {'class': "cardMainInfo__content"})
        if len(purchase_name) > 0:
            purchase_name = purchase_name[0].text
        else:
            purchase_name = ""
        resp_dict["name"] = purchase_name
        start_price = soup.find_all("span", {'class': "cardMainInfo__content cost"})
        if len(start_price) > 0:
            try:
                start_price = int(''.join(start_price[0].text.strip().split(',')[0].split()))
            except:
                start_price = -1
        else:
            start_price = -1
        currency = "RUB"
        resp_dict["max_price"] = start_price
        resp_dict["currency"] = currency
        el = soup.find_all("div", {'class': "cardMainInfo__section col-6"})
        if len(el) > 0:
            try:
                update_dt = el[1].find("span", {"class": "cardMainInfo__content"}).text.strip()
                update_dt = datetime.strptime(update_dt, '%d.%M.%Y')
            except:
                update_dt = datetime.now()
        else:
            update_dt = datetime.now()
        resp_dict["update_dt"] = update_dt
        #winer_list = soup.find_all('table', {'class': 'blockInfo__table tableBlock'})
        if len(reestr_header) == 0:
            return resp_dict
        else:
            el = reestr_header[0]
            contract_url = el.parent.parent.findNext("tbody").findNext("tr").findNext("td").findNext('a').get("href")
            inn_info = await extract_info_from_contract(session, contract_url)
            return {**resp_dict, **inn_info}

async def main():
    start_time = time.time()
    conn_string = "host=\'"+ creds.PGHOST + "\' port="+ "5432" + " dbname=\'"+ creds.PGDATABASE +"\' user=\'" + creds.PGUSER \
    + "\' password=\'" + creds.PGPASSWORD + "\'"
    conn = psycopg2.connect(conn_string, sslmode=creds.SSLMODE)
    print("Database connected!")
    purchase_query = '''
            INSERT INTO {} ("regNumber", "name", "max_price", "currency", "update_dt", "code")
            VALUES (%(regNumber)s, %(name)s, %(max_price)s, %(currency)s, %(update_dt)s, %(code)s);
            '''.format(config["purchases_table_name"])
    contract_query = '''
            INSERT INTO {} ("reestrNumber", "purchase", "price", "executor")
            VALUES (%(reestrNumber)s, %(regNumber)s, %(price)s, %(inn)s);
            '''.format(config["contracts_table_name"])
    company_query = '''
            INSERT INTO {} ("inn", "name")
            VALUES (%(inn)s, %(company_name)s);
            '''.format(config["companies_table_name"])
    company_attribute_query = '''
            INSERT INTO {} ("company_inn", "attribute_type", "attribute_value")
            VALUES (%(company_inn)s, %(attribute_type)s, %(attribute_value)s);
            '''.format(config["company_attributes_table_name"])
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
                # print(res) if config["print"] else None
                for item in res:
                    cur.execute(purchase_query, item)
                    if "inn" in item:
                        if item["inn"] not in unique_inns:
                            cur.execute(company_query, item)
                            unique_inns.add(item["inn"])
                            attribute_dict = {"company_inn": item["inn"], "attribute_type": "phone", "attribute_value": item["phone"]}
                            cur.execute(company_attribute_query, attribute_dict)
                            attribute_dict = {"company_inn": item["inn"], "attribute_type": "address", "attribute_value": item["address"]}
                            cur.execute(company_attribute_query, attribute_dict)
                            attribute_dict = {"company_inn": item["inn"], "attribute_type": "email", "attribute_value": item["email"]}
                            cur.execute(company_attribute_query, attribute_dict)
                        cur.execute(contract_query, item)
                    print(item) if config["print"] else None
                conn.commit()
                cur.close()
                time.sleep(config["time_sleep"])
            except:
                conn.rollback()
                cur.close()
                print(time.time(), "Sleeping")
                time.sleep(5)
                print(time.time(), "Saving unique inns")
                with open(config["unique_inns_filename"], 'wb') as handle:
                    pickle.dump(unique_inns, handle, protocol=pickle.HIGHEST_PROTOCOL)
                print(time.time(), "Continue")
                continue
    conn.close()
    with open(config["unique_inns_filename"], 'wb') as handle:
        pickle.dump(unique_inns, handle, protocol=pickle.HIGHEST_PROTOCOL)
    print("All time is ", time.time() - start_time)


asyncio.run(main())