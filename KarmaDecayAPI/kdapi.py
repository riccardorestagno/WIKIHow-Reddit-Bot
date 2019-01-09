import re
import requests
from urllib import parse
from lxml import etree
from .rateLimited import RateLimited
from functools import lru_cache

class KDItem:
    def __init__(self):
        self.title = None
        self.link = None
        self.imgur_link = None
        self.user = None
        self.subreddit = None
        self.similarity = None
        self.time = None
        self.score = None
        self.comments = None
    def __str__(self):
        return str(self.__dict__)

# extracts text from a tree 'root', using xpath selector 'selector' and optionally a regex
# return None if the selector finds no items
def _extract(root,selector,regex=None):
    item = root.xpath(selector)
    string = None
    if len(item) == 0:
        return None
    elif hasattr(item[0], 'text'):
        string = item[0].text
    else:
        string = item[0]

    if regex is None:
        return string
    else:
         match = re.search(regex, " ".join(string.split()))
         return match.group() if match is not None else None

_defaultVal = None
def setDefault(val): # the default value for when a piece of info is not available
    global _defaultVal
    _defaultVal = val

def _cast(func,num):
    try:
        return func(num)
    except Exception:
        global _defaultVal
        return _defaultVal

def _extractItem(root):
    item = KDItem()
    info = root.xpath("td[@class='info']")[0]

    item.imgur_link = _extract(root,"td[@class='img']/a/@href")
    item.title = _extract(info,"div[@class='title']/a")
    item.link = _extract(info,"div[@class='title']/a/@href")
    
    item.similarity = _cast(float,_extract(info,"div[@class='similar']/span[@class='fr']", r'[\d\.]+(?=\%)'))
    item.time = _extract(info,"div[@class='submitted']",r'(?<=submitted\s).*(?=\sago)')
    item.user = _extract(info,"div[@class='submitted']/a[1]")
    item.subreddit = _extract(info,"div[@class='submitted']/a[2]")
    item.score = _cast(int,_extract(info,"div[not(@class)]/div[@class='votes']/b",r'[-\d*]+'))
    item.comments = _cast(int,_extract(info,"div[not(@class)]/div[@class='comments']/b",r'[-\d*]+'))
    return item

@RateLimited(1.0) # allow no more than one call every two seconds
@lru_cache(maxsize=100) # cache recent results 
def check(url, subreddit, getLessSimilar=False):

    is_reddit_link = parse.urlparse(url if url.startswith("http://") else "http://" + url).hostname.split('.')[-2:][0] == "reddit"
    
    kd_url = "http://karmadecay.com/search?kdtoolver=b1&q=" + parse.quote(url) + "&subreddit=" + subreddit
    
    # user agent string for Chrome 41, karmadecay.com returns 401 for a "python-requests..." user agent
    user_agent = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.87 Safari/537.36'}
    try:
        request = requests.get(kd_url, headers=user_agent, timeout=15)
    except:
        return []
    html = request.content
    request.close()

    tree = etree.HTML(html)
    
    output = []

    if not is_reddit_link: # only add the top item if the link was not a reddit link (to avoid duplicates)
        headResult = tree.xpath("//tr[@class='s']")
        if len(headResult) > 0: # make sure there's actually a head item
            headItem = _extractItem(headResult[0])
            if headItem.link is not None: # make sure there's a link present, sometimes there's not one
                output.append(headItem)

    results = tree.xpath("//tr[@class='ls' or @class='lsi']/preceding::tr[@class='result']")

    output.extend([_extractItem(result) for result in results])

    if not getLessSimilar:
        return output

    lessSimilar = tree.xpath("//tr[@class='ls' or @class='lsi']/following::tr[@class='result']")
    lsOutput = [_extractItem(result) for result in lessSimilar]
    return (output,lsOutput)