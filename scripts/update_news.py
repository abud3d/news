#!/usr/bin/env python3
import json, os, re, time, urllib.parse, urllib.request, urllib.error, xml.etree.ElementTree as ET
from html.parser import HTMLParser
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
OUT = os.path.join(DATA_DIR, "news.json")
os.makedirs(DATA_DIR, exist_ok=True)

QUERIES = {
 "Saudi Arabia news":"أخبار السعودية",
 "Saudi Arabia artificial intelligence":"الذكاء الاصطناعي السعودية",
 "Saudi Arabia technology":"تقنية السعودية",
 "Saudi Arabia economy":"اقتصاد السعودية",
 "Saudi Arabia startups":"الشركات الناشئة السعودية",
 "السعودية سياحة":"السياحة السعودية",
 "السعودية تعليم":"التعليم السعودية",
 "وظائف السعودية وظائف شاغرة توظيف":"وظائف السعودية",
 "السعودية صحة":"الصحة السعودية",
 "العالم أخبار":"أخبار العالم",
 "عربي أخبار":"أخبار عربية",
 "SPORT_KSA":"دوري روشن السعودي الهلال النصر الاتحاد الأهلي أخبار",
 "SPORT_AFC":"دوري أبطال آسيا للنخبة الهلال الأهلي أخبار",
}
CITIES = {
 "Riyadh":("الرياض",24.7136,46.6753),"Buraydah":("بريدة",26.3592,43.9818),
 "Hail":("حائل",27.5114,41.7208),"Jeddah":("جدة",21.4858,39.1925),
 "Makkah":("مكة المكرمة",21.3891,39.8579),"Madinah":("المدينة المنورة",24.5247,39.5692),
 "Dammam":("الدمام",26.4207,50.0888),"Abha":("أبها",18.2164,42.5053),
 "Tabuk":("تبوك",28.3838,36.5550),"Taif":("الطائف",21.2703,40.4158),
 "Jazan":("جازان",16.8892,42.5511),"Najran":("نجران",17.5650,44.2289),
 "AlBaha":("الباحة",20.0129,41.4677),"Sakaka":("سكاكا",29.9697,40.2064),
 "Arar":("عرعر",30.9753,41.0381), "AlKhobar":("الخبر",26.2172,50.1971)
}
CITY_NEWS_QUERIES = {
 "Riyadh":'"الرياض" السعودية أخبار',
 "Buraydah":'"القصيم" OR "بريدة" السعودية أخبار',
 "Hail":'"حائل" السعودية أخبار',
 "Jeddah":'"جدة" السعودية أخبار',
 "Makkah":'"مكة المكرمة" OR "مكة" السعودية أخبار',
 "Madinah":'"المدينة المنورة" OR "المدينة" السعودية أخبار',
 "Dammam":'"الدمام" OR "المنطقة الشرقية" السعودية أخبار',
 "Abha":'"أبها" OR "عسير" السعودية أخبار',
 "Tabuk":'"تبوك" السعودية أخبار',
 "Taif":'"الطائف" السعودية أخبار',
 "Jazan":'"جازان" السعودية أخبار',
 "Najran":'"نجران" السعودية أخبار',
 "AlBaha":'"الباحة" السعودية أخبار',
 "Sakaka":'"سكاكا" OR "الجوف" السعودية أخبار',
 "Arar":'"عرعر" OR "الحدود الشمالية" السعودية أخبار',
 "AlKhobar":'"الخبر" OR "الظهران" السعودية أخبار',
}
UA = "SaudiAI-NewsBot/1.0 (+https://abud3d.github.io/news/)"
def get(url, timeout=12):
 req=urllib.request.Request(url, headers={"User-Agent":UA,"Accept":"application/rss+xml, application/xml, application/json, text/xml"})
 with urllib.request.urlopen(req, timeout=timeout) as r:
  if r.status != 200: raise RuntimeError("HTTP "+str(r.status))
  return r.read()

def clean(s):
 return re.sub(r"\s+"," ", re.sub(r"<[^>]+>"," ",unescape(s or ""))).strip()

class MetaDescriptionParser(HTMLParser):
 def __init__(self):
  super().__init__(); self.description=""
 def handle_starttag(self, tag, attrs):
  if tag.lower()!="meta" or self.description: return
  a={k.lower():v for k,v in attrs if k and v}
  key=(a.get("property") or a.get("name") or "").lower()
  if key in ("og:description","twitter:description","description"):
   self.description=clean(a.get("content",""))

def page_excerpt(url):
 try:
  req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html"})
  with urllib.request.urlopen(req,timeout=5) as response:
   if response.status!=200 or "text/html" not in response.headers.get("Content-Type","").lower(): return ""
   raw=response.read(256000).decode(response.headers.get_content_charset() or "utf-8","replace")
  parser=MetaDescriptionParser(); parser.feed(raw)
  return parser.description[:300]
 except Exception:
  return ""

def enrich_excerpts(rows):
 checked=0
 for item in rows:
  item["description"]=clean(item.get("description",""))[:300]
  if not item["description"] and item.get("url") and checked<3:
   checked+=1
   item["description"]=page_excerpt(item["url"])
 return rows

def parse_rss(url, source_override=None):
 root=ET.fromstring(get(url))
 rows=[]
 for item in root.findall(".//item"):
  title=clean(item.findtext("title"))
  link=(item.findtext("link") or "").strip()
  if not title or not link: continue
  pub=item.findtext("pubDate") or item.findtext("{http://www.w3.org/2005/Atom}published") or ""
  desc=clean(item.findtext("description"))
  src=item.find("source")
  source=source_override or (clean(src.text) if src is not None and src.text else "")
  rows.append({"title":title,"url":link,"source":source or "الناشر الأصلي","date":pub,"description":desc[:350]})
 return rows

def fetch_google(q):
 url="https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":q,"hl":"ar","gl":"SA","ceid":"SA:ar"})
 rows=parse_rss(url)
 for x in rows:
  if not x["source"]:
   parts=x["title"].rsplit(" - ",1)
   x["source"]=parts[-1] if len(parts)>1 else "الناشر الأصلي"
 return rows

def fetch_hacker():
 j=json.loads(get("https://hn.algolia.com/api/v1/search?tags=front_page"))
 return [{"title":x.get("title",""),"url":x.get("url") or "https://news.ycombinator.com/item?id="+str(x.get("objectID","")),
 "source":"Hacker News","date":x.get("created_at",""),"description":clean(x.get("story_text",""))[:350]}
 for x in j.get("hits",[]) if x.get("title")]

def fetch_weather(city):
 name,lat,lon=city
 url="https://api.open-meteo.com/v1/forecast?"+urllib.parse.urlencode({"latitude":lat,"longitude":lon,"current":"temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m","daily":"temperature_2m_max,temperature_2m_min,precipitation_probability_max","forecast_days":3,"timezone":"Asia/Riyadh"})
 j=json.loads(get(url))
 cur=j["current"]; daily=j["daily"]
 codes={0:"صافٍ",1:"غائم جزئياً",2:"غائم جزئياً",3:"غائم",45:"ضباب",48:"ضباب",51:"رذاذ خفيف",53:"رذاذ",55:"رذاذ كثيف",61:"مطر خفيف",63:"مطر",65:"مطر غزير",71:"ثلوج خفيفة",80:"زخات مطر",81:"زخات مطر",82:"زخات غزيرة",95:"عواصف رعدية"}
 title=f"طقس {name}: {codes.get(cur.get('weather_code'),'حالة جوية')} · {cur.get('temperature_2m')}°"
 desc=f"المحسوس {cur.get('apparent_temperature')}° · الرطوبة {cur.get('relative_humidity_2m')}% · الرياح {cur.get('wind_speed_10m')} كم/س. "
 desc += " | ".join(f"{daily['time'][i]}: العظمى {daily['temperature_2m_max'][i]}° والصغرى {daily['temperature_2m_min'][i]}°، احتمال المطر {daily['precipitation_probability_max'][i]}%" for i in range(min(3,len(daily.get("time",[])))))
 return {"title":title,"url":"https://open-meteo.com/","source":"Open-Meteo","date":cur.get("time",""),"description":desc}

def key_for_url(x):
 return (x.get("url") or "").strip().lower()

def merge(old, new, limit=50):
 seen=set(); out=[]
 for x in new+old:
  k=key_for_url(x) or re.sub(r"\W+","",x.get("title","").lower())
  if not k or k in seen: continue
  seen.add(k); out.append(x)
 return out[:limit]

try:
 with open(OUT,encoding="utf-8") as f: previous=json.load(f)
except Exception: previous={"categories":{},"weather":{}}
result={"schema":1,"updated_at":datetime.now(timezone.utc).isoformat(),"categories":{},"weather":{},"city_news":{},"weather_news":{}}
errors=[]
def category(key, fn):
 old=previous.get("categories",{}).get(key,{})
 try:
  fresh=fn()
  fresh=enrich_excerpts(fresh)
  result["categories"][key]={"items":merge(old.get("items",[]),fresh),"updated_at":result["updated_at"],"status":"ok" if fresh else "ok_empty","new_items":len(fresh)}
 except Exception as e:
  errors.append(key+": "+str(e))
  result["categories"][key]={"items":old.get("items",[]),"updated_at":old.get("updated_at",""),"status":"stale" if old.get("items") else "unavailable","error":str(e)[:180]}

for key,q in QUERIES.items():
 category(key, fetch_hacker if key=="HACKER_NEWS" else (lambda q=q: fetch_google(q)))
category("__CYBER__",lambda:parse_rss("https://thehackernews.com/feeds/posts/default?alt=rss","The Hacker News"))
category("HACKER_NEWS",fetch_hacker)
# Refresh weather, city headlines and city-weather headlines concurrently.
def refresh_weather(code, city):
 old=previous.get("weather",{}).get(code)
 try: return ("weather",code,fetch_weather(city),None)
 except Exception as e: return ("weather",code,old,str(e))

def refresh_city_feed(kind, code, query):
 old=previous.get(kind,{}).get(code,{})
 try:
  fresh=fetch_google(query)
  data={"items":merge(old.get("items",[]),fresh),"updated_at":result["updated_at"],"status":"ok" if fresh else "ok_empty","new_items":len(fresh)}
  return (kind,code,data,None)
 except Exception as e:
  data={"items":old.get("items",[]),"updated_at":old.get("updated_at",""),"status":"stale" if old.get("items") else "unavailable","error":str(e)[:180]}
  return (kind,code,data,str(e))

tasks=[]
for code,city in CITIES.items():
 tasks.append(("weather",code,city))
 tasks.append(("city_news",code,CITY_NEWS_QUERIES[code]))
 name=city[0]
 tasks.append(("weather_news",code,f'"{name}" طقس OR "حالة الطقس" {name}'))

def run_task(task):
 kind,code,arg=task
 if kind=="weather": return refresh_weather(code,arg)
 return refresh_city_feed(kind,code,arg)

with ThreadPoolExecutor(max_workers=10) as pool:
 futures=[pool.submit(run_task,task) for task in tasks]
 for future in as_completed(futures):
  kind,code,data,error=future.result()
  if kind=="weather":
   if data: result["weather"][code]=data
   else: errors.append("weather "+code+": "+str(error))
  else:
   result[kind][code]=data
   if error: errors.append(kind+" "+code+": "+str(error))
result["errors"]=errors
with open(OUT,"w",encoding="utf-8") as f: json.dump(result,f,ensure_ascii=False,indent=2)
print("Updated",len(result["categories"]),"feeds and",len(result["weather"]),"weather locations; errors:",len(errors))
for e in errors: print("WARN:",e)
