#!/usr/bin/python
import bs4 as bs
import urllib
import re
import threading
import argparse

from lxml import etree
from dateutil.parser import parse

class URLOpener(urllib.FancyURLopener):
    version = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; it; rv:1.8.1.11) Gecko/20071127 Firefox/2.0.0.11'


class Source:
    def __init__(self, url, maxresults=0, src=None):
        self.url = url
        self.src = None
        self.torrents = []
        self.tableRegex = "ULed by (.+)"
        self.max = maxresults
        self.domain = re.search("(https|http)://[a-z0-9\.]+/", url).group(0)[:-1]
        print "URL: ", url
    def getRawSource(self):
        src = URLOpener().open(self.url).read()
	return src

    def getBsObj(self):
        if self.src is not None:
            return bs.BeautifulSoup(self.src)
        else:
            return bs.BeautifulSoup(self.getRawSource())

    def getAllTorrents(self):
        threadList = []
        tables = self.getBsObj().find_all("tr")
        if self.max == 0 or self.max > len(tables):
            for torrentTable in tables:
                thr = threading.Thread(target=self._torrentTableParser, args=(torrentTable,))
                thr.start()
                threadList.append(thr)

        else:
            for torrentTable in tables[:self.max+1]:
                thr = threading.Thread(target=self._torrentTableParser, args=(torrentTable,))
                thr.start()
                threadList.append(thr)

        while 1:
            if len(threadList) != 0:
                for thread in threadList:
                    if not thread.is_alive():
                        threadList.remove(thread)
            else:
                return self.torrents

    def _torrentTableParser(self, torrentTable):
        torrent = Torrent()
        for link in torrentTable.find_all("a"):
            linkObj = str(link.get("href"))
            if linkObj.startswith("magnet:"):
                torrent.setMagnetLink(linkObj)
                torrent.setHash(linkObj.split(":")[3].split("&")[0].upper())

            elif linkObj.startswith("/torrent/"):
                torrent.setGUID(self.domain + linkObj)
                tpbInfoSrc = Source(self.domain + linkObj)
                for dd in tpbInfoSrc.getBsObj().find_all("dd"):
                    dd = re.sub(r'[^\x20-\x7e]', " ", str(dd))
                    if "Bytes" in str(dd):
                        torrent.setSize(re.findall("\((\d+)  Bytes\)", dd)[0])
                    else:
                        dd = re.sub("<dd>", "", dd)
                        dd = re.sub("</dd>", "", dd)
                        try:
                            torrent.setTime(parse(dd).strftime("%s"))
                        except ValueError:
                            pass
                        except TypeError:
                            pass

            if link.get("class") == ["detLink"]:
                torrent.setTitle(link.text)

        for font in torrentTable.find_all("font"):
            text = re.sub(r'[^\x20-\x7e]', " ", font.text)
            data = re.findall(self.tableRegex, text)
            torrent.setUploader(data[0])

        self.torrents.append(torrent)

class Torrent:
    def __init__(self, name=None, size=None, magnetLink=None, guid=None, time=None, hash=None):
        self.torrentName = name
        self.size = size
        self.magnetLink = magnetLink
        self.guid = guid #aka torrent link
        self.uploaded = time
        self.hash = hash

    def getTorrentName(self):
        return self.torrentName

    def getSize(self):
        return self.size

    def getMagnetLink(self):
        return self.magnetLink

    def getGUID(self):
        return self.guid

    def getTitle(self):
        return self.title

    def getUploader(self):
        return self.uploader

    def getHash(self):
        return self.hash

    def setTitle(self, title):
        self.title = title

    def setTorrentName(self, name):
        self.torrentName = name

    def setSize(self, size):
        self.size = size

    def setHash(self, hash):
        self.hash = hash

    def setMagnetLink(self, link):
        self.magnetLink = link

    def setGUID(self, guid):
        self.guid = guid

    def setTime(self,time):
        self.uploaded = time

    def setUploader(self, uploader):
        self.uploader = uploader


class RSS:
    def __init__(self, rsstitle, torrents=[]):
        self.rsstitle = rsstitle
        self.torrents = torrents
        self.namespaces = {"dc" : "http://purl.org/dc/elements/1.1/"}
        self.root = etree.Element("rss", nsmap=self.namespaces)
        self.root.set("version", "2.0")

    def createBasicRSS(self):
        self.channelEl = etree.SubElement(self.root, "channel")
        etree.SubElement(self.channelEl, "title").text = self.rsstitle
        etree.SubElement(self.channelEl, "link").text = "http://nullfluid.com"
        etree.SubElement(self.channelEl, "description").text = "The Pirate Bay search RSS"
        etree.SubElement(self.channelEl, "language").text = "en"
        etree.SubElement(self.channelEl, "pubDate").text = "Now"
        etree.SubElement(self.channelEl, "lastBuildDate").text = "Now"
        etree.SubElement(self.channelEl, "generator").text = "Skuom RSS Generator 0.1"

    def createRSSItems(self):
        for torrent in self.torrents:
            item = etree.SubElement(self.channelEl, "item")
            etree.SubElement(item, "title").text = etree.CDATA(torrent.getTitle())
            etree.SubElement(item, "link").text = etree.CDATA(torrent.getMagnetLink())
            etree.SubElement(item, "comments").text = etree.CDATA(torrent.getGUID())
            etree.SubElement(item, "{%s}creator" % (self.namespaces["dc"])).text = etree.CDATA(torrent.getUploader())

            torrentEl = etree.SubElement(item, "torrent")
            torrentEl.set("xmlns", "http://xmlns.ezrss.it/0.1/")
            etree.SubElement(torrentEl, "contentLength").text = torrent.getSize()
            etree.SubElement(torrentEl, "infoHash").text = torrent.getHash()
            etree.SubElement(torrentEl, "magnetURI").text = etree.CDATA(torrent.getMagnetLink())

    def getRSS(self):
        return etree.tostring(self.root)


parser = argparse.ArgumentParser()
parser.add_argument('search', metavar="search", default="pineapple")
parser.add_argument('max', metavar="maxresults", type=int, default=0)


args = parser.parse_args()


###############
#Example Usage#
###############

a = Source("https://thepiratebay.se/search/%s/0/7/0" % (urllib.quote(urllib.unquote(args.search))),
           maxresults=args.max).getAllTorrents()
a.pop(0)

b = RSS("%s - NullFluid" % (urllib.unquote(args.search)), a)
b.createBasicRSS()
b.createRSSItems()
print b.getRSS()
