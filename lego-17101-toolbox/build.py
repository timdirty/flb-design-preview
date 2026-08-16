#!/usr/bin/env python3
from __future__ import annotations

import csv, hashlib, html, io, json, os, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
INV = ROOT / "inventory.csv"
IMG = ROOT / "images"
STATIC = ROOT / "static"
REPORTS = ROOT / "reports"
for d in (IMG, STATIC, REPORTS): d.mkdir(parents=True, exist_ok=True)

TRAYS = {
 "A": ["Black","Bright Red","Brick Yellow","Reddish Brown","Flame Yellowish Orange","Sand Yellow","Transparent Red"],
 "B": ["White","Medium Stone Grey","Bright Yellow","Bright Blue","Light Purple","Bright Yellowish Green","Silver Metallic","Transparent Light Blue"],
 "C": ["Bright Orange","Dark Azur","Dark Stone Grey","Dark Green","Medium Azur","Multicombination","Transparent Blue","Transparent Bright Orange"],
}
COLOURS = {
 "Black":"#252525","White":"#f4f4f0","Bright Orange":"#f57c00","Dark Azur":"#0097a7",
 "Dark Stone Grey":"#676b70","Medium Stone Grey":"#a5a5a5","Bright Blue":"#1565c0",
 "Bright Red":"#d32f2f","Bright Yellow":"#fbc02d","Brick Yellow":"#d6b77b",
 "Dark Green":"#2e6b3a","Reddish Brown":"#795548","Bright Yellowish Green":"#9ccc65",
 "Flame Yellowish Orange":"#ffb74d","Light Purple":"#b39ddb","Medium Azur":"#4fc3f7",
 "Sand Yellow":"#c7b58a","Silver Metallic":"#b0bec5","Transparent Blue":"#64b5f6",
 "Transparent Bright Orange":"#ffcc80","Transparent Light Blue":"#b3e5fc","Transparent Red":"#ef9a9a",
 "Multicombination":"#c7c7d1",
}
PROOF = ["6283413","6283415","6240610","6097664","6325504","6185551","4495935","370826","4177431","4121715","300126","6078296"]

def group(row):
    n=row["ElementName"].upper(); c=row["Category"]
    if c in ("Bricks","Plates"): return "BUILD"
    if any(k in n for k in ("BEAM","AXLE","GEAR","TOOTHED","PIN","PEG","BUSH","CONNECTOR","JOINT")): return "MECHANISM"
    return "SPECIAL"

def session():
    s=requests.Session(); retry=Retry(total=5,connect=5,read=5,backoff_factor=.8,status_forcelist=(429,500,502,503,504),allowed_methods=frozenset(["GET"]))
    s.mount("https://",HTTPAdapter(max_retries=retry)); s.headers.update({"User-Agent":"Mozilla/5.0 FLB-17101-GitHub-Pages/2.0","Accept":"image/*,*/*;q=.8"}); return s

def sources(row):
    e=row["ElementID"]; rel=row.get("ImageURL","")
    return [u for u in [
      f"https://www.lego.com{rel}" if rel else "",
      f"https://www.lego.com/cdn/product-assets/element.img.lod5photo.192x192/{e}.jpg",
      f"https://images.brickset.com/parts/{e}.jpg",
      f"https://images.brickset.com/parts/large/{e}.jpg",
      f"https://cdn.rebrickable.com/media/parts/elements/{e}.jpg",
    ] if u]

def good(path):
    try:
        with Image.open(path) as im: im.verify()
        return path.stat().st_size>400
    except Exception: return False

def download(row):
    out=IMG/f"{row['ElementID']}.webp"
    if good(out): return {"element":row["ElementID"],"status":"cached","source":"repo"}
    s=session(); errors=[]
    for url in sources(row):
        try:
            r=s.get(url,timeout=(15,45),allow_redirects=True)
            if r.status_code!=200: errors.append(f"{url} HTTP {r.status_code}"); continue
            with Image.open(io.BytesIO(r.content)) as im:
                im.load(); im=im.convert("RGBA"); im.thumbnail((640,640),Image.Resampling.LANCZOS); im.save(out,"WEBP",quality=92,method=6)
            if good(out): return {"element":row["ElementID"],"status":"downloaded","source":r.url,"sha256":hashlib.sha256(out.read_bytes()).hexdigest()}
        except Exception as exc: errors.append(f"{url} {type(exc).__name__}: {exc}")
    return {"element":row["ElementID"],"status":"failed","errors":errors}

def fnt(size,bold=False):
    p="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(p,size) if Path(p).exists() else ImageFont.load_default()

def proof_png(rows):
    selected=[next(r for r in rows if r["ElementID"]==e) for e in PROOF]
    W,H=2400,1800; canvas=Image.new("RGB",(W,H),(238,240,242)); d=ImageDraw.Draw(canvas)
    d.text((70,30),"LEGO BOOST 17101 · 12 REAL PART IMAGE PROOF",font=fnt(42,True),fill=(25,27,30))
    cw=(W-224)//4; ch=(H-236)//3
    for i,r in enumerate(selected):
        x=70+(i%4)*(cw+28); y=125+(i//4)*(ch+28)
        d.rounded_rectangle((x,y,x+cw,y+ch),radius=28,fill="white",outline=(215,220,225),width=3)
        with Image.open(IMG/f"{r['ElementID']}.webp") as im:
            im=ImageOps.contain(im.convert("RGBA"),(cw-48,ch-120),Image.Resampling.LANCZOS); canvas.paste(im,(x+(cw-im.width)//2,y+18+(ch-120-im.height)//2),im)
        d.text((x+18,y+ch-88),r["ElementName"][:42],font=fnt(18,True),fill=(25,27,30))
        d.text((x+18,y+ch-49),f"{r['Colour']} · Element {r['ElementID']} · Design {r['DesignID']} · ×{r['Qty']}",font=fnt(14),fill=(90,96,104))
    canvas.save(STATIC/"proof-12.png",optimize=True)

def esc(x): return html.escape(str(x),quote=True)
def card(r):
    data=esc(json.dumps({"name":r["ElementName"],"colour":r["Colour"],"qty":int(r["Qty"]),"category":r["Category"],"group":r["group"],"design":r["DesignID"],"element":r["ElementID"],"image":f"images/{r['ElementID']}.webp"},ensure_ascii=False))
    return f'<button class="part g-{r["group"].lower()}" data-part="{data}" onclick="openPart(this)"><span class="badge">{r["group"][0]}</span><img src="images/{r["ElementID"]}.webp" alt="{esc(r["ElementName"])}"><span class="qty">×{r["Qty"]}</span><strong>{r["DesignID"]}</strong><span class="notch"></span></button>'

def page(rows, summary):
    proof=''.join(f'<article><img src="images/{r["ElementID"]}.webp"><strong>{esc(r["ElementName"])}</strong><small>{r["Colour"]} · Element {r["ElementID"]} · ×{r["Qty"]}</small></article>' for r in [next(r for r in rows if r["ElementID"]==e) for e in PROOF])
    trays=[]
    for t,colours in TRAYS.items():
        sections=[]
        for colour in colours:
            cr=[r for r in rows if r["Colour"]==colour]
            if not cr: continue
            groups=[]
            for g,label in (("BUILD","BUILD｜磚／板"),("MECHANISM","MECHANISM｜梁／軸／齒輪／連接件"),("SPECIAL","SPECIAL｜動力／輪組／特殊件")):
                gr=[r for r in cr if r["group"]==g]
                if gr: groups.append(f'<div class="func"><h4>{label}</h4><div class="grid">{"".join(card(r) for r in gr)}</div></div>')
            colour_hex=COLOURS.get(colour,"#aaa"); pieces=sum(int(r["Qty"]) for r in cr)
            sections.append(f'<section class="colour" style="--c:{colour_hex}"><h3>{esc(colour)} <span>{pieces} pcs · {len(cr)} homes</span></h3>{"".join(groups)}</section>')
        trays.append(f'<div class="tray" id="tray-{t}"><div class="trayhead">Tray {t} · {sum(len([r for r in rows if r["Colour"]==c]) for c in colours)} homes · {sum(int(r["Qty"]) for r in rows if r["Colour"] in colours)} pieces</div>{"".join(sections)}</div>')
    html_text=f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FLB BOOST 17101 真實零件配置</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#eef0f2;color:#17191c;font-family:-apple-system,BlinkMacSystemFont,"Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif}}header{{position:sticky;top:0;z-index:50;background:#fffffff2;backdrop-filter:blur(16px);border-bottom:1px solid #d9dde1}}.head{{max-width:1500px;margin:auto;padding:13px 18px;display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}}h1{{font-size:19px;margin:0}}.ok{{background:#dff6e7;color:#135f2c;padding:8px 12px;border-radius:999px;font-weight:900;font-size:12px}}main{{max-width:1500px;margin:auto;padding:20px 12px 60px}}.notice{{background:#e4f5e9;border:1px solid #92cda5;border-radius:14px;padding:13px 15px;margin-bottom:18px;line-height:1.6}}.proof{{background:#fff;border-radius:18px;padding:16px;box-shadow:0 12px 45px #0001;margin-bottom:18px}}.proofgrid{{display:grid;grid-template-columns:repeat(6,1fr);gap:9px}}article{{border:1px solid #dde1e5;border-radius:12px;padding:8px;min-width:0;background:#fbfbfc}}article img{{width:100%;aspect-ratio:1;object-fit:contain;background:#fff}}article strong,article small{{display:block}}article strong{{font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}article small{{font-size:8px;color:#777}}.tabs{{position:sticky;top:75px;z-index:40;display:flex;gap:7px;width:max-content;background:#eef0f2dd;padding:7px;border-radius:12px}}.tab{{border:0;background:#fff;border-radius:9px;padding:9px 18px;font-weight:900}}.tab.active{{background:#17191c;color:#fff}}.tray{{display:none}}.tray.active{{display:block}}.trayhead{{font-size:18px;font-weight:900;margin:18px 0 10px}}.colour{{background:color-mix(in srgb,var(--c),white 84%);border:2px solid var(--c);border-radius:18px;padding:12px;margin:12px 0}}.colour h3{{margin:0 0 10px;background:var(--c);padding:9px 12px;border-radius:12px;color:#17191c}}.colour h3 span{{float:right;font-size:.75em;opacity:.75}}.func{{background:#ffffffc9;border-radius:14px;padding:10px;margin-top:9px}}.func h4{{margin:0 0 8px;font-size:12px;color:#4d545c}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(88px,1fr));gap:8px}}.part{{position:relative;min-height:108px;border-radius:12px;background:#fff;padding:8px;border:2px solid #aaa;box-shadow:0 2px 7px #0001;cursor:zoom-in}}.part img{{width:100%;height:76px;object-fit:contain}}.part strong{{display:block;font:700 10px monospace;color:#555}}.g-build{{border-color:#3d7bd9}}.g-mechanism{{border-color:#e38b27}}.g-special{{border-color:#8b5bc7}}.qty,.badge{{position:absolute;border-radius:999px;min-width:24px;height:24px;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:900;z-index:2}}.qty{{right:-4px;top:-5px;background:#17191c;color:white}}.badge{{left:-4px;top:-5px;background:white;border:1px solid #777}}.notch{{position:absolute;bottom:-1px;left:36%;width:28%;height:10px;background:#eef0f2;border:1px solid #777;border-bottom:0;border-radius:99px 99px 0 0}}.modal{{display:none;position:fixed;inset:0;z-index:100;background:#0b0d10c9;align-items:center;justify-content:center;padding:18px}}.modal.open{{display:flex}}.modalcard{{width:min(94vw,820px);max-height:94vh;overflow:auto;background:white;border-radius:20px;padding:20px}}.close{{float:right;border:0;border-radius:999px;width:38px;height:38px;font-size:22px}}.modalgrid{{clear:both;display:grid;grid-template-columns:1.1fr .9fr;gap:22px}}.modalgrid img{{width:100%;aspect-ratio:1;object-fit:contain;border:1px solid #ddd;border-radius:16px}}table{{width:100%;border-collapse:collapse}}td{{padding:8px 3px;border-bottom:1px solid #eee}}td:first-child{{color:#777}}@media(max-width:850px){{.proofgrid{{grid-template-columns:repeat(3,1fr)}}.modalgrid{{grid-template-columns:1fr}}}}@media(max-width:500px){{.proofgrid{{grid-template-columns:repeat(2,1fr)}}.grid{{grid-template-columns:repeat(3,1fr)}}main{{padding:12px 6px 40px}}}}
</style></head><body><header><div class="head"><div><h1>FLB LEGO BOOST 17101 真實零件配置</h1><small>GitHub 自託管 · 不再熱連結 · 218 個 Home / 850 件</small></div><div class="ok">✓ {summary["success"]} / 218 圖片已下載驗證</div></div></header><main><div class="notice"><strong>這版是真的把圖片下載到 GitHub。</strong> 手機開啟時只讀這個 GitHub Pages 網站自己的 `images/`，不再向 LEGO 或 Brickset 即時取圖。</div><section class="proof"><h2>12 個關鍵零件真實圖片</h2><div class="proofgrid">{proof}</div><p><a href="static/proof-12.png">開啟靜態大圖</a></p></section><div class="tabs"><button class="tab active" onclick="show('A',this)">Tray A</button><button class="tab" onclick="show('B',this)">Tray B</button><button class="tab" onclick="show('C',this)">Tray C</button></div>{"".join(trays)}</main><div class="modal" id="modal" onclick="if(event.target.id==='modal')closeM()"><div class="modalcard"><button class="close" onclick="closeM()">×</button><div class="modalgrid"><img id="mi"><div><h2 id="mn"></h2><table><tr><td>顏色</td><td id="mc"></td></tr><tr><td>數量</td><td id="mq"></td></tr><tr><td>功能</td><td id="mg"></td></tr><tr><td>類別</td><td id="mcat"></td></tr><tr><td>Design ID</td><td id="md"></td></tr><tr><td>Element ID</td><td id="me"></td></tr></table></div></div></div></div><script>function show(t,b){{document.querySelectorAll('.tray').forEach(x=>x.classList.remove('active'));document.getElementById('tray-'+t).classList.add('active');document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active')}}function openPart(b){{const d=JSON.parse(b.dataset.part);mi.src=d.image;mn.textContent=d.name;mc.textContent=d.colour;mq.textContent='×'+d.qty;mg.textContent=d.group;mcat.textContent=d.category;md.textContent=d.design;me.textContent=d.element;modal.classList.add('open')}}function closeM(){{modal.classList.remove('open')}}document.getElementById('tray-A').classList.add('active');</script></body></html>'''
    (ROOT/"index.html").write_text(html_text,encoding="utf-8")
    (ROOT/"proof.html").write_text(html_text,encoding="utf-8")

def main():
    if not INV.exists(): raise SystemExit("inventory.csv missing")
    rows=list(csv.DictReader(open(INV,encoding="utf-8-sig")))
    if len(rows)!=218 or sum(int(r["Qty"]) for r in rows)!=850: raise SystemExit(f"bad inventory: {len(rows)} rows")
    for r in rows: r["group"]=group(r)
    results=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        fut={pool.submit(download,r):r for r in rows}
        for i,f in enumerate(as_completed(fut),1):
            result=f.result(); results.append(result); print(f"[{i:03d}/218] {result['element']} {result['status']}",flush=True)
    failed=[r for r in results if r["status"]=="failed"]
    summary={"total":218,"success":218-len(failed),"failed":len(failed),"inventory_pieces":850,"design_colour_homes":218,"generated_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
    (REPORTS/"verification.json").write_text(json.dumps({"summary":summary,"results":sorted(results,key=lambda x:x["element"])},ensure_ascii=False,indent=2),encoding="utf-8")
    if failed: print(json.dumps(failed,ensure_ascii=False,indent=2)); raise SystemExit(f"failed images: {len(failed)}")
    proof_png(rows); page(rows,summary)
    (ROOT/"README.md").write_text("# BOOST 17101 self-hosted real parts review\n\n218 verified local images.\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__": main()
