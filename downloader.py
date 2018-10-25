import threading
import time
import os
import uuid
import subprocess
import shutil

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

    def _show(self):
        with progressbar.ProgressBar(max_value=self.size) as bar:
            while True:
                bar.update(self.dsize)
                if self.dsize == self.size:
                    return
                time.sleep(0.5)

    def _download(self, k):
        raise NotImplementedError()

    def _concat(self):
        raise NotImplementedError()

    #Only work for linux or MacOS
    def _write(self, r, name, start):
        with open(name, 'wb+') as f:
            f.seek(start)
            for data in r.iter_content(chunk_size=1024*1024):
                f.write(data)
                with self.dsize_lock:
                    self.dsize += len(data)


    def start(self):
        threads = [threading.Thread(target=self._download, args=(i,)) for i in range(self.thread_num)]
        threads.append(threading.Thread(target=self._show))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if type(self) is MultiDownloader:
            self._concat()


class SingleDownloader(Downloader):
    def __init__(self, durl, agent, name, size, headers, thread_num = 10):
        super().__init__(agent, name, size, headers, thread_num)
        self.durl = durl
        self.frag = self.size // self.thread_num

    def _download(self, k):
        start = self.frag * k
        end = self.frag * (k + 1) - 1
        headers = self.headers.copy()
        if k == self.thread_num - 1:
            headers['range'] = 'bytes=%s-' % start
        else:
            headers['range'] = 'bytes=%s-%s' % (start, end)
        url = self.durl['backup_url'][0]

        with self.agent.get(url, headers=headers, stream=True, verify=False) as r:
            if r.status_code == 200 or 206:
                self._write(r, self.name, start)


class MultiDownloader(Downloader):
    def __init__(self, durls, agent, name, size, headers, thread_num = 10):
        super().__init__(agent, name, size, headers, thread_num)
        self.durls = durls
        if self.thread_num <= len(durls) * 2:
            self.durl_thread_num = 2
        else:
            self.durl_thread_num = thread_num // len(durls)
        self.thread_num = self.durl_thread_num * len(durls)
        self.temp_dir = str(uuid.uuid1())
        os.mkdir(self.temp_dir)
        self.filelist = os.path.join(self.temp_dir, 'filelist.txt')

        with open(self.filelist, 'w') as f:
            for i in range(len(durls)):
                f.write("file 'temp.%s'\n" % i)

    def _download(self, k):
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

        if "backup_url" in self.durls[order]:
            url = self.durls[order]['backup_url'][0]
        else:
            url = self.durls[order]['url']

        with self.agent.get(url, headers=headers, stream=True, verify=False) as r:
            if r.status_code == 200 or 206:
                path = os.path.join(self.temp_dir, "temp" + '.' + str(order))
                self._write(r, path, start)

    def _concat(self):
        print("starting concat!")
        subprocess.check_call(['ffmpeg', '-f', 'concat', '-i', self.filelist, '-c', 'copy', self.name], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        shutil.rmtree(self.temp_dir)