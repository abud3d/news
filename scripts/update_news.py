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
 "Arar":("عرعر",30.9753,41.0381), "AlKhobar":("الخبر",26.2172,50.1971),"AlAhsa":("الأحساء",25.3830,49.5860),
 "Saihat":("سيهات",26.4850,50.0400),"ArRass":("الرس",25.8690,43.4970),
 "Majmaah":("المجمعة",25.9000,45.3500)
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
 "AlAhsa":'"الأحساء" OR "الهفوف" السعودية أخبار',
 "Saihat":'"سيهات" السعودية أخبار',
 "ArRass":'"الرس" السعودية أخبار',
 "Majmaah":'"المجمعة" السعودية أخبار',
}
CITY_CLUBS = {
 "Riyadh":["الهلال","النصر","الشباب","الرياض","الدرعية"],
 "Jeddah":["الاتحاد","الأهلي"],
 "Dammam":["الاتفاق"],
 "AlKhobar":["القادسية"],
 "Buraydah":["التعاون"],
 "Abha":["أبها"],
 "Tabuk":["نيوم"],
 "AlAhsa":["الفتح"],
 "Saihat":["الخليج"],
 "ArRass":["الحزم","الخلود"],
 "Majmaah":["الفيحاء","الفيصلي"],
}
UA = "SaudiAI-NewsBot/1.0 (+https://abud3d.github.io/news/)"

# مصادر تحريرية محددة؛ RSS المباشر أولاً، والبحث المقيد بنطاق الناشر عند غياب موجز موثق.
SOURCE_REGISTRY = {
 "واس": {"domain":"spa.gov.sa","feed":None},
 "سبق": {"domain":"sabq.org","feed":None},
 "عكاظ": {"domain":"okaz.com.sa","feed":"https://www.okaz.com.sa/rss"},
 "الجزيرة": {"domain":"al-jazirah.com","feed":"https://www.al-jazirah.com/rss/ln.xml"},
 "الوطن": {"domain":"alwatan.com.sa","feed":"https://www.alwatan.com.sa/rssFeed/1"},
 "المرصد": {"domain":"al-marsd.com","feed":"https://al-marsd.com/public/rssFeed/1"},
 "صحيفة الرياض": {"domain":"alriyadh.com","feed":None},
 "العربية": {"domain":"alarabiya.net","feed":None},
 "الجزيرة نت": {"domain":"aljazeera.net","feed":"https://www.aljazeera.net/rss"},
 "عاجل": {"domain":"ajel.sa","feed":"https://ajel.sa/rss.xml"},
 "الشرق الأوسط": {"domain":"aawsat.com","feed":"https://aawsat.com/feed/news"},
 "CNN": {"domain":"arabic.cnn.com","feed":"https://arabic.cnn.com/api/v1/rss/rss.xml"},
 "جريدة المدينة": {"domain":"al-madina.com","feed":"https://www.al-madina.com/rssFeed/193"},
 "BBC": {"domain":"bbcarabic.com","feed":"https://feeds.bbci.co.uk/arabic/rss.xml"},
 "الحدث": {"domain":"alhadath.net","feed":None},
 "GOAL": {"domain":"goal.com","feed":None},
 "Investing": {"domain":"investing.com","feed":None},
 "أرقام": {"domain":"argaam.com","feed":None},
 "عالم التقنية": {"domain":"tech-wd.com","feed":None},
 "أخبار 24": {"domain":"akhbaar24.com","feed":None},
}
SOURCE_DOMAINS = [x["domain"] for x in SOURCE_REGISTRY.values()]

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
 nodes=root.findall(".//item")
 if not nodes: nodes=root.findall(".//{http://www.w3.org/2005/Atom}entry")
 for item in nodes:
  def val(tag):
   x=item.find(tag)
   return (x.text or "").strip() if x is not None else ""
  title=clean(val("title") or val("{http://www.w3.org/2005/Atom}title"))
  link=val("link")
  if not link:
   atom_link=item.find("{http://www.w3.org/2005/Atom}link")
   if atom_link is not None: link=atom_link.attrib.get("href","")
  if not title or not link: continue
  pub=val("pubDate") or val("published") or val("updated") or val("{http://www.w3.org/2005/Atom}published") or val("{http://www.w3.org/2005/Atom}updated")
  desc=clean(val("description") or val("{http://www.w3.org/2005/Atom}summary") or val("{http://www.w3.org/2005/Atom}content"))
  src=item.find("source")
  source=source_override or (clean(src.text) if src is not None and src.text else "")
  rows.append({"title":title,"url":link,"source":source or "الناشر الأصلي","date":pub,"description":desc[:350]})
 return rows

def fetch_google(q):
 url="https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":q,"hl":"ar","gl":"SA","ceid":"SA:ar"})
 rows=parse_rss(url)
 for x in rows:
  if not x["source"] or x["source"]=="الناشر الأصلي":
   parts=x["title"].rsplit(" - ",1)
   x["source"]=parts[-1] if len(parts)>1 else "الناشر الأصلي"
 return rows

def fetch_source_registry():
 results={}; statuses={}
 def one(name,cfg):
  method="بحث مقيد بنطاق الناشر"
  rows=[]
  if cfg.get("feed"):
   try:
    rows=parse_rss(cfg["feed"],name)
    if rows: method="RSS مباشر"
   except Exception:
    rows=[]
   if not rows:
    method="بحث مقيد بنطاق الناشر (بديل RSS)"
    rows=fetch_google("site:"+cfg["domain"]+" أخبار السعودية")
  else:
   rows=fetch_google("site:"+cfg["domain"]+" أخبار السعودية")
  # بحث Google News مقيد بـ site:domain؛ روابط RSS قد تكون روابط تحويل news.google.com وليست نطاق الناشر مباشرة.
  for x in rows: x["source"]=name
  return name,rows,{"status":"ok" if rows else "ok_empty","method":method,"items":len(rows),"checked_at":datetime.now(timezone.utc).isoformat()}
 with ThreadPoolExecutor(max_workers=4) as pool:
  futures={pool.submit(one,n,c):n for n,c in SOURCE_REGISTRY.items()}
  for f in as_completed(futures):
   name=futures[f]
   try:
    n,rows,status=f.result();results[n]=rows;statuses[n]=status
   except Exception as e:
    old=(previous.get("source_cache") or {}).get(name,[])
    results[name]=old
    statuses[name]={"status":"stale" if old else "unavailable","method":"RSS مباشر" if SOURCE_REGISTRY[name].get("feed") else "بحث مقيد بنطاق الناشر","items":len(old),"checked_at":datetime.now(timezone.utc).isoformat(),"error":str(e)[:180]}
 return results,statuses

def editorial_query(q):
 # Google News is the primary discovery engine. Keep the original broad query:
 # publisher/domain restrictions can hide valid stories and sharply reduce results.
 return fetch_google(q)

TECH_SOURCES = {
 "Android Authority":"https://www.androidauthority.com/feed/",
 "GSMArena":"https://www.gsmarena.com/rss-news-reviews.php3",
 "NASA":"https://www.nasa.gov/feed/",
 "Ars Technica":"https://feeds.arstechnica.com/arstechnica/index",
 "WIRED":"https://www.wired.com/feed/rss",
}
TECH_DOMAINS=["androidauthority.com","gsmarena.com","sciencedaily.com","arstechnica.com","wired.com","engadget.com","cnet.com","9to5google.com"]

def fetch_technology():
 rows=[]
 # موجزات متخصصة مباشرة لتغطية العلوم والتقنية والهواتف.
 for name,url in TECH_SOURCES.items():
  try:
   feed_rows=parse_rss(url,name)
   rows.extend(feed_rows)
   print("TECH_SOURCE:",name,"ok items:",len(feed_rows))
  except Exception as e:
   print("TECH_SOURCE:",name,"unavailable:",str(e)[:120])
 # Google News search remains broad; do not restrict results to a fixed domain list.
 queries=[
  'هواتف جوالات سامسونج آيفون Apple Samsung smartphone',
  'علوم اكتشاف علمي تكنولوجيا تقنية artificial intelligence science technology'
 ]
 for q in queries:
  try: rows.extend(fetch_google(q))
  except Exception as e: print("TECH_SEARCH: unavailable:",str(e)[:120])
 for item in rows:
  if not item.get("source") or item["source"]=="الناشر الأصلي":
   host=urllib.parse.urlparse(item.get("url","")).netloc.lower().removeprefix("www.")
   item["source"]=next((d for d in TECH_DOMAINS if host.endswith(d)),host or "مصدر تقني")
 return merge([],rows,limit=100)

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
result={"schema":2,"updated_at":datetime.now(timezone.utc).isoformat(),"categories":{},"weather":{},"city_news":{},"weather_news":{},"source_status":{},"source_cache":{}}
errors=[]
fetched_news_keys=set()
def register_fetched(rows):
 for item in rows:
  key=key_for_url(item) or re.sub(r"\W+","",item.get("title","").lower())
  if key: fetched_news_keys.add(key)
source_cache,source_status=fetch_source_registry()
result["source_status"]=source_status
for source_name,source_info in source_status.items():
 print("SOURCE:",source_name,source_info.get("status"),source_info.get("method"),"items:",source_info.get("items",0))
 if source_info.get("status") in ("stale","unavailable"):
  errors.append("source "+source_name+": "+source_info.get("error","unavailable"))
result["source_cache"]={k:merge((previous.get("source_cache") or {}).get(k,[]),v,limit=30) for k,v in source_cache.items()}
all_editorial=[x for rows in source_cache.values() for x in rows]
def category(key, fn):
 old=previous.get("categories",{}).get(key,{})
 try:
  fresh=fn()
  fresh=enrich_excerpts(fresh)
  register_fetched(fresh)
  old_items=[{**item,"is_new":False} for item in old.get("items",[])]
  old_keys={key_for_url(item) or re.sub(r"\\W+","",item.get("title","").lower()) for item in old_items}
  fresh=[{**item,"is_new":(key_for_url(item) or re.sub(r"\\W+","",item.get("title","").lower())) not in old_keys} for item in fresh]
  result["categories"][key]={"items":merge(old_items,fresh),"updated_at":result["updated_at"],"status":"ok" if fresh else "ok_empty","new_items":sum(1 for item in fresh if item["is_new"])}
 except Exception as e:
  errors.append(key+": "+str(e))
  result["categories"][key]={"items":[{**item,"is_new":False} for item in old.get("items",[])],"updated_at":old.get("updated_at",""),"status":"stale" if old.get("items") else "unavailable","error":str(e)[:180]}

for key,q in QUERIES.items():
 if key not in ("SPORT_KSA","SPORT_AFC"):
  if key=="Saudi Arabia technology":
   category(key,fetch_technology)
  else:
   category(key, fetch_hacker if key=="HACKER_NEWS" else (lambda q=q,k=key: merge((all_editorial if k=="Saudi Arabia news" else []),editorial_query(q),limit=50)))
category("__CYBER__",lambda:parse_rss("https://thehackernews.com/feeds/posts/default?alt=rss","The Hacker News"))
category("HACKER_NEWS",fetch_hacker)

# تصنيف موضوعي متعدد الوسوم: يقرأ العنوان والوصف، ويسمح بإدراج الخبر في أكثر من قسم عند انطباقه.
TOPIC_KEYWORDS = {
 "Saudi Arabia artificial intelligence": {
  "ذكاء اصطناعي":3,"الذكاء الاصطناعي":3,"تعلم آلي":3,"تعلم عميق":3,"نماذج لغوية":3,"نموذج لغوي":3,
  "ذكاء توليدي":3,"توليد الصور":2,"روبوت محادثة":2,"شات جي بي تي":3,"تشات جي بي تي":3,"وكلاء الذكاء":3,
  "شبكات عصبية":2,"معالجة اللغة الطبيعية":3,"رؤية حاسوبية":3
 },
 "Saudi Arabia technology": {
  "تقنية":2,"تكنولوجيا":2,"تقني":2,"هاتف ذكي":2,"هواتف ذكية":2,"جوال":2,"هواتف":1,"أجهزة":1,
  "تطبيق":2,"تطبيقات":2,"برمجيات":2,"برنامج":1,"منصة رقمية":3,"حوسبة سحابية":3,"معالج":2,
  "رقائق إلكترونية":3,"أشباه الموصلات":3,"إنترنت الأشياء":3,"اتصالات":2,"شبكات الجيل":3,
  "إطلاق جهاز":2,"نظام تشغيل":3
 },
 "Saudi Arabia economy": {
  "اقتصاد":3,"اقتصادي":3,"الاقتصادية":2,"الاقتصاد":3,"أسهم":3,"سوق الأسهم":3,"تداول":2,"البورصة":3,
  "مؤشر السوق":3,"أرباح":3,"إيرادات":3,"خسائر":2,"ميزانية":3,"الموازنة":3,"تضخم":3,"فائدة":2,
  "أسعار الفائدة":3,"البنك المركزي":3,"ساما":2,"نفط":2,"أسعار النفط":3,"خام برنت":3,"الطاقة":1,
  "استثمار":2,"استثمارات":2,"تمويل":2,"استحواذ":3,"اندماج":2,"صفقة":2,"صادرات":3,"واردات":3,
  "الناتج المحلي":3,"القطاع الخاص":2,"القطاع المصرفي":3,"مصرف":2,"بنك":1,"ريال":1,
  "سندات":3,"صكوك":3,"اكتتاب":3,"توزيعات نقدية":3,"سعر السهم":3,"أسعار الذهب":2,
  "الذهب":1,"الدين العام":3,"الإنفاق الحكومي":3,"الإيرادات الحكومية":3
 },
 "Saudi Arabia startups": {
  "شركة ناشئة":3,"الشركات الناشئة":3,"ريادة الأعمال":3,"رائد أعمال":2,"رأس المال الجريء":3,
  "جولة تمويل":3,"جولة استثمارية":3,"تمويل أولي":3,"مسرعة أعمال":3,"حاضنة أعمال":3,
  "مشروع ناشئ":3,"منشأة ناشئة":3,"استثمار جريء":3,"تأسيس شركة":2
 },
 "السعودية سياحة": {
  "سياحة":3,"سياحي":3,"سياحية":3,"السياح":3,"سائح":2,"وجهة سياحية":3,"وجهات سياحية":3,
  "فنادق":2,"فندق":2,"منتجع":2,"منتجعات":2,"موسم سياحي":3,"تأشيرة سياحية":3,
  "السياحة الداخلية":3,"التراث":1,"المواقع الأثرية":2,"رحلات سياحية":3
 },
 "السعودية تعليم": {
  "تعليم":3,"التعليم":3,"وزارة التعليم":3,"جامعة":2,"جامعات":2,"مدرسة":2,"مدارس":2,
  "طالب":1,"طلاب":2,"اختبارات":2,"قبول جامعي":3,"مناهج":2,"ابتعاث":3,"ابتعاث خارجي":3,
  "أكاديمي":2,"التدريب التقني":2,"التعليم الجامعي":3,"الفصل الدراسي":2
 },
 "وظائف السعودية وظائف شاغرة توظيف": {
  "وظائف":3,"وظيفة":2,"توظيف":3,"توظيف":3,"فرص عمل":3,"شواغر":3,"وظائف شاغرة":3,
  "سوق العمل":2,"باحثين عن عمل":3,"باحث عن عمل":3,"التوطين":2,"التدريب المنتهي بالتوظيف":3
 },
 "السعودية صحة": {
  "الصحة":2,"صحي":2,"صحية":2,"وزارة الصحة":3,"مستشفى":2,"مستشفيات":2,"طبي":2,"طبية":2,
  "دواء":2,"أدوية":2,"علاج":2,"لقاح":2,"مرض":2,"أمراض":2,"وباء":3,"جائحة":3,
  "عملية جراحية":2,"رعاية صحية":3,"التأمين الصحي":3,"الطب":1,"الأطباء":2
 },
 "العالم أخبار": {
  "دولي":2,"دولية":2,"عالمي":2,"عالمية":2,"الأمم المتحدة":3,"مجلس الأمن":3,
  "الولايات المتحدة":3,"أمريكا":2,"بريطانيا":2,"فرنسا":2,"ألمانيا":2,"روسيا":2,
  "أوكرانيا":2,"الصين":2,"اليابان":2,"الاتحاد الأوروبي":3,"البيت الأبيض":3,
  "الكونغرس":2,"الانتخابات الأمريكية":3,"الحرب في":2,"قمة مجموعة العشرين":3
 },
 "عربي أخبار": {
  "مصر":2,"الأردن":2,"لبنان":2,"العراق":2,"سوريا":2,"اليمن":2,"فلسطين":2,
  "السودان":2,"ليبيا":2,"تونس":2,"المغرب":2,"الجزائر":2,"موريتانيا":2,
  "قطر":2,"الكويت":2,"البحرين":2,"الإمارات":2,"سلطنة عمان":2,
  "جامعة الدول العربية":3,"الدول العربية":3,"العالم العربي":3
 }
}
TOPIC_ALIASES = {
 "Saudi Arabia artificial intelligence":"Saudi Arabia artificial intelligence",
 "Saudi Arabia technology":"Saudi Arabia technology",
 "Saudi Arabia economy":"Saudi Arabia economy",
 "Saudi Arabia startups":"Saudi Arabia startups",
 "السعودية سياحة":"السعودية سياحة",
 "السعودية تعليم":"السعودية تعليم",
 "وظائف السعودية وظائف شاغرة توظيف":"وظائف السعودية وظائف شاغرة توظيف",
 "السعودية صحة":"السعودية صحة",
 "العالم أخبار":"العالم أخبار",
 "عربي أخبار":"عربي أخبار"
}
def classify_topics(item):
 text=clean((item.get("title","") or "")+" "+(item.get("description","") or "")).lower()
 text=text.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه","ـ":""}))
 matched=set()
 for key, terms in TOPIC_KEYWORDS.items():
  score=0
  for phrase, weight in terms.items():
   normalized=phrase.translate(str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ة":"ه","ـ":""})).lower()
   if normalized in text: score+=weight
  if score>=2: matched.add(key)
 return matched

# نجمع الأخبار التي جُمعت في الدورة نفسها، ثم نعيد توزيعها موضوعياً على الأقسام.
# نحافظ على الأخبار غير المصنفة بوضوح، ولا نمس أقسام الرياضة والأمن السيبراني.
editorial_keys=list(TOPIC_ALIASES.keys())
editorial_pool=[]
for source_key in editorial_keys:
 editorial_pool.extend(result.get("categories",{}).get(source_key,{}).get("items",[]))
editorial_pool=merge([],editorial_pool,limit=500)
for target_key in editorial_keys:
 current=result.get("categories",{}).get(target_key,{})
 current_items=current.get("items",[])
 kept=[]
 for item in current_items:
  topics=classify_topics(item)
  if not topics or target_key in topics: kept.append(item)
 additions=[]
 for item in editorial_pool:
  if target_key in classify_topics(item): additions.append({**item,"is_new":item.get("is_new",False)})
 combined=merge(kept,additions,limit=50)
 old_keys={key_for_url(x) for x in current_items}
 for item in combined:
  if key_for_url(item) not in old_keys and "is_new" not in item: item["is_new"]=True
 current["items"]=combined
 current["new_items"]=sum(1 for item in combined if item.get("is_new"))
 current["status"]="ok" if combined else current.get("status","ok_empty")
 result["categories"][target_key]=current
 print("TOPIC_CLASSIFIER:",target_key,"items:",len(combined),"added:",len(additions))
# الرياضة: بحث مقيد بالمصادر الرياضية والأندية، مع موجزات الأقسام الرياضية المتاحة.
def fetch_sports(query):
 # Use broad Google News search, matching the original working collection logic.
 rows=fetch_google(query)
 try: rows+=parse_rss("https://www.alwatan.com.sa/rssFeed/3","الوطن")
 except Exception: pass
 try: rows+=parse_rss("https://www.al-jazirah.com/rss/sp.xml","الجزيرة")
 except Exception: pass
 return merge([],rows,limit=50)
category("SPORT_KSA",lambda:fetch_sports("دوري روشن السعودي الهلال النصر الاتحاد الأهلي الشباب مباريات اليوم"))
category("SPORT_AFC",lambda:fetch_sports("دوري أبطال آسيا للنخبة الهلال الأهلي الاتحاد مباريات"))
# Refresh weather, city headlines and city-weather headlines concurrently.
def refresh_weather(code, city):
 old=previous.get("weather",{}).get(code)
 try: return ("weather",code,fetch_weather(city),None)
 except Exception as e:
  fallback=old or {"title":f"طقس {city[0]}: غير متاح مؤقتاً","url":"https://open-meteo.com/","source":"Open-Meteo","date":"","description":"تعذر جلب حالة الطقس لهذه المدينة في آخر دورة تحديث.","status":"unavailable"}
  return ("weather",code,fallback,str(e))

def is_riyadh_newspaper(item):
 source=clean(item.get("source","")).replace(" ","").lower()
 url=urllib.parse.unquote(item.get("url","")).lower()
 return ("صحيفةالرياض" in source or "جريدةالرياض" in source or
         "alriyadh.com" in url)

def refresh_city_feed(kind, code, query):
 old=previous.get(kind,{}).get(code,{})
 try:
  # أخبار المدينة العامة، ثم أخبار أنديتها المرتبطة بالمدينة في الموجز نفسه.
  fresh=editorial_query(query)
  clubs=CITY_CLUBS.get(code,[])
  if clubs:
   club_query=" OR ".join('"'+club+'"' for club in clubs)
   fresh+=editorial_query("("+club_query+") (نادي OR مباراة OR دوري OR فريق OR رياضة)")
  register_fetched(fresh)
  if code=="Riyadh":
   # استبعاد صحيفة الرياض وجريدة الرياض كمصدر، لا ككلمة في عنوان الخبر.
   fresh=[item for item in fresh if not is_riyadh_newspaper(item)]
  old_items=[{**item,"is_new":False} for item in old.get("items",[])]
  old_keys={key_for_url(item) or re.sub(r"\\W+","",item.get("title","").lower()) for item in old_items}
  fresh=[{**item,"is_new":(key_for_url(item) or re.sub(r"\\W+","",item.get("title","").lower())) not in old_keys} for item in fresh]
  combined=merge(old_items,fresh)
  if code=="Riyadh":
   combined=[item for item in combined if not is_riyadh_newspaper(item)]
  data={"items":combined,"updated_at":result["updated_at"],"status":"ok" if fresh else "ok_empty","new_items":len(fresh)}
  return (kind,code,data,None)
 except Exception as e:
  data={"items":[{**item,"is_new":False} for item in old.get("items",[])],"updated_at":old.get("updated_at",""),"status":"stale" if old.get("items") else "unavailable","error":str(e)[:180]}
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

with ThreadPoolExecutor(max_workers=5) as pool:
 futures=[pool.submit(run_task,task) for task in tasks]
 for future in as_completed(futures):
  kind,code,data,error=future.result()
  if kind=="weather":
   if data: result["weather"][code]=data
   else: errors.append("weather "+code+": "+str(error))
  else:
   result[kind][code]=data
   if error: errors.append(kind+" "+code+": "+str(error))
result["fetched_news_count"]=len(fetched_news_keys)
result["errors"]=errors
with open(OUT,"w",encoding="utf-8") as f: json.dump(result,f,ensure_ascii=False,indent=2)
print("Updated",len(result["categories"]),"feeds and",len(result["weather"]),"weather locations; errors:",len(errors))
for e in errors: print("WARN:",e)
