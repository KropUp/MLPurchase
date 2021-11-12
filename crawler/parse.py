import time
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import pandas as pd
import yaml
import os
import sys
from tqdm import tqdm
import datetime

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

async def extract_info_from_contract(session, contract_url, purch):
    contract_url = 'https://zakupki.gov.ru' + contract_url
    async with session.get(contract_url, headers=headers) as resp:
            contract_page_text = await resp.text()
            #contract_page_text = contract_page_text.decode('utf-8')
            soup = BeautifulSoup(contract_page_text, features="lxml")
            info_dict = {"purch": purch, "inn": "","name": "", "phone": "", "address": "", "email": ""}
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
                    info_dict["name"] = name[1].strip() \
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

            return info_dict

async def parse_logic(session, purch):
    url = "https://zakupki.gov.ru/epz/order/notice/ep44/view/supplier-results.html?regNumber=" + purch
    async with session.get(url, headers=headers) as resp:
        text = await resp.text()
        soup = BeautifulSoup(text, features="lxml")
        reestr_header = soup.find_all("th", {"class": "tableBlock__col tableBlock__col_header"}, text="Номер реестровой записи")
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
                start_price = None
        currency = "RUB"
        el = soup.find_all("div", {'class': "cardMainInfo__section col-6"})
        if len(el) > 0:
            update_dt = el[1].find("span", {"class": "cardMainInfo__content"}).text.strip()
            update_dt = datetime.strptime(update_dt, '%d.%M.%Y')
        else:
            update_dt = None
        #winer_list = soup.find_all('table', {'class': 'blockInfo__table tableBlock'})
        info_dict = {"purch": purch, "inn": "","name": "", "phone": "", "address": "", "email": ""}
        if len(reestr_header) == 0:
            return info_dict
        else:
            el = reestr_header[0]
            contract_url = el.parent.parent.findNext("tbody").findNext("tr").findNext("td").findNext('a').get("href")
            return await extract_info_from_contract(session, contract_url, purch)

async def main():
    start_time = time.time()
    chunk_size = config["async_chunk_size"]
    df = pd.DataFrame(columns=["purch", "inn", "name", "phone", "address", "email"])
    async with aiohttp.ClientSession() as session:
        epoch = 1
        count_epochs = len(purch_list) // chunk_size + ((len(purch_list) // chunk_size) > 0)
        count_epochs_to_write_on_disk = config["count_epochs_to_write_on_disk"]
        print("Count batches is", count_epochs)
        for epoch in tqdm(range(count_epochs)):
            try:
                print("Epoch №", epoch) if config["print"] else None
                tasks = []
                chunk = purch_list[chunk_size * epoch : chunk_size * (epoch + 1)]
                for purch in chunk:
                    tasks.append(parse_logic(session, purch))
                res = await asyncio.gather(*tasks)
                print(res) if config["print"] else None
                df = df.append(res)
                if (epoch % count_epochs_to_write_on_disk) == 0:
                    print("DataFrame saved") if config["print"] else None
                    filename_to_save = config["output_format_str"].format(config["chunk_num"])
                    df.to_csv(filename_to_save, index=False)
                epoch += 1
                time.sleep(config["time_sleep"])
            except:
                print(time.time(), "Sleeping")
                time.sleep(60)
                print(time.time(), "Continue")
                continue
    print("All time is ", time.time() - start_time)


asyncio.run(main())