import aiohttp
import asyncio
import time
import pandas as pd
import os
from bs4 import BeautifulSoup
from typing import List

DATA_PATH = "/purchase/data"

start_time = time.time()

headers = {'sec-ch-ua': '" Not;A Brand";v="99", "Google Chrome";v="91", "Chromium";v="91"',
           'sec-ch-ua-mobile':'0',
           'Upgrade-Insecure-Requests': '1',
           'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

list_inn: List[str] = []

async def extract_inn_from_contract(session, contract_url, purch):
    contract_url = 'https://zakupki.gov.ru' + contract_url
    async with session.get(contract_url, headers=headers) as resp:
            contract_page_text = await resp.text()
            soup = BeautifulSoup(contract_page_text, features="lxml")
            spans = soup.find_all('span')
            ind_cur = -1
            for span in spans:
                if span.text == 'ИНН:': 
                    ind_cur = spans.index(span)+1
                    break
            if ind_cur == -1:
                return 
            else:
                f = open('data.txt', 'a')
                f.write(spans[ind_cur].text + "\n")
                f.close()
                return spans[ind_cur].text


async def parse_logic(session, purch):
    url = "https://zakupki.gov.ru/epz/order/notice/ea44/view/supplier-results.html?regNumber=" + purch
    async with session.get(url, headers=headers) as resp:
        text = await resp.text()
        soup = BeautifulSoup(text, features="lxml")
        winer_list = soup.find_all('table', {'class': 'blockInfo__table tableBlock'})
        if len(winer_list) > 3:
            soup = BeautifulSoup(str(winer_list[3]), features="lxml")
        elif len(winer_list) == 3:
            soup = BeautifulSoup(str(winer_list[2]), features="lxml")
        else:
            return
        contract_link = soup.find('a')
        try:
            contract_url = contract_link.get('href')
        except Exception:
            return
        return await extract_inn_from_contract(session, contract_url, purch)

df = pd.read_excel(os.path.join(DATA_PATH, 'INN_OUT_31_08_2021.xlsx'))
# Data preparing
df['purch'] = df['Реестровый номер закупки'].apply(lambda x:x[1:])
df = df.loc[df['Закупки по']=='44-ФЗ']
df = df.loc[df['Этап закупки']=='Определение поставщика завершено']
print("Shape of purchaces df is", df.shape)
all_count = df.shape[0]

# async def main():
#     count = 0
#     global all_count
#     print("Whole", all_count // 10, "loops")
#     for count in range(all_count // 10):
#         print(count, "/", all_count // 10, "iteration")
#         start_batch_time = time.time()
#         try:
#             async with aiohttp.ClientSession() as session:
#                 tasks = []
#                 for purch in df['purch'][count * 10 : (count + 1) * 10]:
#                     tasks.append(parse_logic(session, purch))
#                 print("Tasks builded")
#                 res = await asyncio.gather(*tasks)
#                 print("--- %s seconds ---" % (time.time() - start_batch_time))
#                 print("Tasks done")
#         except:
#             print("Exception")
#             time.sleep(10)

async def main():
    start_batch_time = time.time()
    try:
        async with aiohttp.ClientSession() as session:
            tasks = []
            for purch in df['purch'][800:830]:
                tasks.append(parse_logic(session, purch))
            print("Tasks builded")
            res = await asyncio.gather(*tasks)
            print("--- %s seconds ---" % (time.time() - start_batch_time))
            print("Tasks done")
    except:
        print("Exception")

asyncio.run(main())
print("--- %s seconds ---" % (time.time() - start_time))