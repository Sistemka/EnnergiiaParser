from gevent import monkey as curious_george
curious_george.patch_all(thread=False, select=False)
import json
import uuid
import os
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import random
import re
import grequests
import requests
import io
import base64
from api import image_manager

proxies = set()

href_pool = set()
items_href_pool = set()
visited_href = set()
items_visited_href = set()

site = 'https://www.ennergiia.com/'


PORT_REGEX = r'>([1-5]?[0-9]{2,4}|6[1-4][0-9]{3}|65[1-4][0-9]{2}|655[1-2][0-9]|6553[1-5])<'
IP_REGEX = r'>(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)<'
IP_PORT_REGEX = r'(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]):[0-9]'


async def fill_proxy_list(site):
    async with aiohttp.ClientSession() as session:
        async with session.get(site) as resp:
            page = await resp.text()
            proxies.update(re.findall(IP_PORT_REGEX, page))
            proxies.update(ip+':'+port for ip, port in zip(
                ['.'.join(ip) for ip in re.findall(IP_REGEX, page)], re.findall(PORT_REGEX, page)))


async def checkproxy(proxy: str):
    async with aiohttp.ClientSession() as session:
        try:
            resp = await session.get("https://google.com", proxy=proxy if "http://" in proxy else "http://"+proxy, timeout=0)
            resp.close()
        except:
            proxies.remove(proxy)


def fill_proxies(fill_proxy=False):
    if fill_proxy:
        with open("proxies.txt", "r") as f:
            tasks = []
            loop = asyncio.get_event_loop()
            for site in f:
                tasks.append(loop.create_task(fill_proxy_list(site)))
            loop.run_until_complete(asyncio.wait(tasks))
            loop.close()
    with open('file.txt', 'r') as f:
        proxies.update(f.read().split('\n'))
    proxies_list = {
        proxy if "http://" in proxy else "http://"+proxy for proxy in proxies}
    proxies.clear()
    proxies.update(proxies_list)
    responses = grequests.map([grequests.get(
        "http://165.22.95.38/", proxies={'http': proxy}, timeout=5) for proxy in proxies])
    for response, proxy in zip(responses, list(proxies)):
        try:
            if response is None:
                proxies.remove(proxy)
        except:
            proxies.remove(proxy)
    print(proxies)


shoes = {'кроссовки',
         "ботинки",
         'кеды',
         'тапочки',
         'сланцы',
         'sneakers', }

top = {'свитер',
       'толстовка',
       'олимпийка',
       'рубашка',
       'лонгслив',
       'поло',
       'футболка',
       'куртка',
       'парка',
       'бомбер',
       'пуховик',
       'анорак',
       'ветровка',
       'аляска',
       'пальто',
       'пиджак',
       'плащ',
       'жилет',
       'платье',
       'джемпер',
       'майка',
       'кардиган',
       'болеро',
       'водолазка',
       'пуловер',
       'футболка-поло',
       'блузка',}

bottom = {'джинсы',
          'брюки',
          'шорты',
          'шорты-плавки',
          'леггинсы' }


def check_sex(text: str):
    text = text.lower()
    if 'муж' in text:
        return 'male'
    elif 'жен' in text:
        return 'female'
    elif 'дет' in text or 'мал' in text or 'дев' in text:
        return 'child'
    elif 'подрост' in text:
        return 'teenager'
    else:
        return 'undefined'


def check_type(text: str):
    text = text.lower()
    words = text.split()
    for word in words:
        if word in top:
            return 'top'
        elif word in bottom:
            return 'bottom'
        elif word in shoes:
            return 'shoes'
    return None

def picture_download(pic_linc: str):
    response = requests.get(pic_linc, proxies={'http': random.sample(proxies, 1)[0]})
    encoded = io.BytesIO(response.content)
    return encoded

def add_catalogues(response):
    href_pool = []
    if response is not None:
        soup = BeautifulSoup(response.text, 'html.parser')
        dicted_json = json.loads(soup.find('div', {'id': "data", 'role': "presentation"}).text.replace(
            'window.__PRELOADED_STATE__=', ''))
        full_menu = dicted_json.get('menuStore').get('menuCategories')
        if full_menu:
            for menu_item in full_menu:
                href_pool.append(
                    (site+'/catalog/'+menu_item.get('uri')).replace('//', '/').replace(':/', '://'))
    return href_pool


def add_items(response):
    if response is not None and response.status_code == 200:
        batch = []
        soup = BeautifulSoup(response.text, 'html.parser')
        dicted_json = json.loads(soup.find('div', {'id': "data", 'role': "presentation"}).text.replace(
            'window.__PRELOADED_STATE__=', ''))
        items = dicted_json.get('productListStore').get('list')
        if len(items)==0:
            print("Empty: %s" % str(response.url))
        for item in items:
            product_info = {"image": None, 'цена': None,
                            'пол': None, 'цвет': None, 'бренд': None, 'link': None, 'type': None}
            product_info['type'] = check_type(item.get('productName'))
            if product_info['type'] and product_info['type'] != 'shoes':
                product_info['link'] = site + 'products/' + item.get('slug')
                for prop in item.get('listingProperties'):
                    prop_name = prop.get("name").lower()
                    if prop_name in product_info.keys():
                        product_info[prop_name] = prop.get('value')
                prices = item.get('prices')
                product_info['цена'] = min([prices[0].get(value) for value in [
                                        'price', 'personalPrice', 'promoPrice'] if prices[0].get(value) is not None])
                image_props = item.get('images')
                product_info['image'] = picture_download(
                    '%s/%s/%s/0/%s.jpg' % (*[image_props.get(value) for value in [
                                                            'baseUrl', 'client', 'imageGroupId']], image_props.get('sizes').get('big')))
                image_manager.upload_image_bytes(product_info)
            else:
                print(item.get('productName'))


def run(site: str, get_proxies: bool = False):
    fill_proxies(get_proxies)
    links_list = add_catalogues(requests.get(site))
    requests_list = [grequests.get(
        link, proxies={'http': random.sample(proxies, 1)[0]}) for link in links_list]
    responses = grequests.map(requests_list)
    for response in responses:
        add_items(response)


run(site=site, get_proxies=True)
