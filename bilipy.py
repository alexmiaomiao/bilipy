#! /usr/local/bin/python3

import re
import json
import sys
import threading
import time

import requests
from bs4 import BeautifulSoup
import progressbar


class Downloader():
    def __init__(self, agent, name, size, headers, thread_num):
        self.dsize = 0
        self.dsize_lock = threading.Lock()
        self.agent = agent
        self.name = name
        self.size = size
        self.headers = headers
        self.thread_num = thread_num

    def show(self):
        with progressbar.ProgressBar(max_value=size) as bar:
            while True:
                bar.update(self.dsize)
                if self.dsize == size:
                    return
                time.sleep(0.5)

    def inner(self, k):
        raise NotImplementedError()

    def start(self):
        threads = [threading.Thread(target=self.inner, args=(i,)) for i in range(self.thread_num)]
        threads.append(threading.Thread(target=self.show))
        for t in threads:
            t.start()
        for t in threads:
            t.join()


class SingleDownloader(Downloader):
    def __init__(self, durl, agent, name, size, headers, thread_num = 10):
        super().__init__(agent, name, size, headers, thread_num)
        self.durl = durl

    def inner(self, k):
        frag = self.size // self.thread_num
        start = frag * k
        end = frag * (k + 1) - 1
        headers = self.headers.copy()
        if k == self.thread_num - 1:
            headers['range'] = 'bytes=%s-' % start
        else:
            headers['range'] = 'bytes=%s-%s' % (start, end)
        url = self.durl['backup_url'][0]

        with self.agent.get(url, headers=headers, stream=True, verify=False) as r:
            if r.status_code == 200 or 206:
                with open(self.name, 'wb+') as f:
                    f.seek(start)
                    for data in r.iter_content(chunk_size=1024*1024):
                        f.write(data)
                        with self.dsize_lock:
                            self.dsize += len(data)


class MultiDownloader(Downloader):
    def __init__(self, durls, agent, name, size, headers, thread_num = 10):
        super().__init__(agent, name, size, headers, thread_num)
        self.durls = durls
        if self.thread_num <= len(durls) * 2:
            self.durl_thread_num = 2
        else:
            self.durl_thread_num = thread_num // len(durls)
        self.thread_num = self.durl_thread_num * len(durls)

    def inner(self, k):
        order = k // self.durl_thread_num
        frag = self.durls[order]['size'] // self.durl_thread_num
        dk = k % self.durl_thread_num
        start = frag * dk
        end = frag * (dk+1) - 1
        headers = self.headers.copy()
        if dk == self.durl_thread_num - 1:
            headers['range'] = 'bytes=%s-' % start
        else:
            headers['range'] = 'bytes=%s-%s' % (start, end)
        url = self.durls[order]['backup_url'][0]

        with self.agent.get(url, headers=headers, stream=True, verify=False) as r:
            if r.status_code == 200 or 206:
                with open(self.name + '.' + str(order), 'wb+') as f:
                    f.seek(start)
                    for data in r.iter_content(chunk_size=1024*1024):
                        f.write(data)
                        with self.dsize_lock:
                            self.dsize += len(data)

    def merge(self):
        pass


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
print(durls)
size = sum(durl['size'] for durl in durls)
name = soup.find(name="title").text.split("_哔哩哔哩")[0] + '.' + playinfo['format']

if len(durls) == 1:
    SingleDownloader(durls[0], s, name, size, headers).start()
else:
    MultiDownloader(durls, s, name, size, headers).start()

