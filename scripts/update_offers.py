#!/usr/bin/env python3
"""Fetch current Saudi offer flyers from SnapFlyer public listings."""
import json, os, re, urllib.request
from html.parser import HTMLParser
from html import unescape
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT=os.path.join(ROOT,"data","offers.json")
SOURCE="https://snapflyer.io/sa/riyadh-city/offers?lang=ar"
BASE="https://snapflyer.io"
UA="SaudiAI-NewsBot/1.0 (+https://abud3d.github.io/news/)"
STORES=("بنده","بندة","العثيم","كارفور","لولو","الدانوب","التميمي","بن داود","إكسترا","اكسترا","جرير","ساكو","نستو","النهدي","صيدليات الدواء","أسواق النخبة","أسواق رامز","المزرعة","هايبر الوفاء","كارفور السعودية")
class Links(HTMLParser):
 def __init__(self):
  super().__init__(); self.stack=[]; self.rows=[]
 def handle_starttag(self,tag,attrs):
  node={"tag":tag.lower(),"attrs":dict(attrs),"text":"","parent":self.stack[-1] if self.stack else None}
  if node["parent"] is not None: node["parent"]["children"].append(node)
  node["children"]=[]
  self.stack.append(node)
 def handle_startendtag(self,tag,attrs):
  self.handle_starttag(tag,attrs); self.handle_endtag(tag)
 def handle_data(self,data):
  for node in self.stack: node["text"]+=data
 def handle_endtag(self,tag):
  tag=tag.lower()
  for i in range(len(self.stack)-1,-1,-1):
   if self.stack[i]["tag"]==tag:
    node=self.stack[i]
    if tag=="a" and node["attrs"].get("href"):
     parent=node["parent"]
     self.rows.append({"href":node["attrs"]["href"],"text":node["text"],"parent":parent})
    del self.stack[i:]
    break
def clean(s):
 return re.sub(r"\s+"," ",unescape(re.sub(r"<[^>]+>"," ",s or ""))).strip()
def main():
 req=urllib.request.Request(SOURCE,headers={"User-Agent":UA,"Accept":"text/html"})
 with urllib.request.urlopen(req,timeout=18) as r:
  if r.status!=200: raise RuntimeError("SnapFlyer HTTP "+str(r.status))
  html=r.read(2_500_000).decode(r.headers.get_content_charset() or "utf-8","replace")
 p=Links(); p.feed(html)
 rows=[]; seen=set()
 for a in p.rows:
  url=urljoin(BASE,a["href"]); u=urlparse(url)
  if u.netloc!="snapflyer.io" or not u.path.startswith("/sa/"): continue
  if any(x in u.path for x in ("/stores/","/products/","/offers","/categories/")): continue
  txt=clean(a["context"] or a["text"])
  if len(txt)<8 or not any(store in txt for store in STORES): continue
  store=next((s for s in STORES if s in txt),"متجر")
  # Card text usually includes store name followed by the flyer title.
  title=txt
  marker=store+" —"
  if marker in txt: title=txt.split(marker,1)[1].strip()
  title=re.sub(r"^SnapFlyer\s*","",title).strip(" ·|—-")
  title=title[:180]
  if not title: continue
  key=url.split("?")[0]
  if key in seen: continue
  seen.add(key)
  rows.append({"title":store+" تطلق عرض: "+title,"url":url,"source":"SnapFlyer · "+store,
   "description":txt[:500],"date":datetime.now(timezone.utc).isoformat(),"category":"عروض المتاجر"})
 if not rows: raise RuntimeError("لم أتعرف على روابط نشرات العروض في صفحة SnapFlyer؛ احتفظنا بالبيانات السابقة")
 print("SnapFlyer links scanned:",len(p.rows),"matching active flyers:",len(rows))
 # Keep currently listed flyers only; listing page is filtered to active flyers.
 result={"updated_at":datetime.now(timezone.utc).isoformat(),"source_url":SOURCE,"items":rows[:100]}
 os.makedirs(os.path.dirname(OUT),exist_ok=True)
 with open(OUT,"w",encoding="utf-8") as f: json.dump(result,f,ensure_ascii=False,indent=2)
 print("SnapFlyer: saved",len(result["items"]),"active flyer links")
if __name__=="__main__": main()
