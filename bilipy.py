#! /usr/local/bin/python3

import re
import json
import sys
import threading

import requests
from bs4 import BeautifulSoup
import progressbar

import downloader

url = sys.argv[1]

headers = {}
headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
headers['Referer'] = 'https://www.bilibili.com'

s = requests.Session()
r = s.get(url, headers=headers)
soup = BeautifulSoup(r.text, features="html.parser")
jss = soup.find(name="script", text=re.compile("^window.__playinfo__"))
playinfo = json.loads(jss.text[20:])
durls = playinfo['durl']
durls.sort(key=lambda x: x['order'])
size = sum(durl['size'] for durl in durls)
name = soup.find(name="title").text.split("_哔哩哔哩")[0] + '.' + durls[0]['url'].split('?')[0].split('.')[-1]

if len(durls) == 1:
    downloader.SingleDownloader(durls[0], s, name, size, headers).start()
else:
    downloader.MultiDownloader(durls, s, name, size, headers).start()
