#!/usr/bin/env python3
import json, os, re, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
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
 "Arar":("عرعر",30.9753,41.0381)
}
UA = "SaudiAI-NewsBot/1.0 (+https://abud3d.github.io/news/)"
def get(url, timeout=25):
 req=urllib.request.Request(url, headers={"User-Agent":UA,"Accept":"application/rss+xml, application/xml, application/json, text/xml"})
 with urllib.request.urlopen(req, timeout=timeout) as r:
  if r.status != 200: raise RuntimeError("HTTP "+str(r.status))
  return r.read()

def clean(s):
 return re.sub(r"\s+"," ", re.sub(r"<[^>]+>"," ",unescape(s or ""))).strip()

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
result={"schema":1,"updated_at":datetime.now(timezone.utc).isoformat(),"categories":{},"weather":{}}
errors=[]
def category(key, fn):
 old=previous.get("categories",{}).get(key,{})
 try:
  fresh=fn()
  if not fresh: raise RuntimeError("المصدر أعاد قائمة فارغة")
  result["categories"][key]={"items":merge(old.get("items",[]),fresh),"updated_at":result["updated_at"],"status":"ok"}
 except Exception as e:
  errors.append(key+": "+str(e))
  result["categories"][key]={"items":old.get("items",[]),"updated_at":old.get("updated_at",""),"status":"stale" if old.get("items") else "unavailable","error":str(e)[:180]}

for key,q in QUERIES.items():
 category(key, fetch_hacker if key=="HACKER_NEWS" else (lambda q=q: fetch_google(q)))
category("__CYBER__",lambda:parse_rss("https://thehackernews.com/feeds/posts/default?alt=rss","The Hacker News"))
category("HACKER_NEWS",fetch_hacker)
for code,city in CITIES.items():
 old=previous.get("weather",{}).get(code)
 try: result["weather"][code]=fetch_weather(city)
 except Exception as e:
  if old: result["weather"][code]=old
  errors.append("weather "+code+": "+str(e))
result["errors"]=errors
with open(OUT,"w",encoding="utf-8") as f: json.dump(result,f,ensure_ascii=False,indent=2)
print("Updated",len(result["categories"]),"feeds and",len(result["weather"]),"weather locations; errors:",len(errors))
for e in errors: print("WARN:",e)
