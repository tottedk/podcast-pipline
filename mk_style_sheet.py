from PIL import Image, ImageDraw, ImageFont
import csv, os
f=ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf",26)
ids=["c01a","c03a","c05b"]; S={"A":"A painterly amber","B":"B photographic teal","C":"C middle ground"}
W,H=960,540; sheet=Image.new("RGB",(3*W+40,3*(H+44)+10),(18,18,18)); d=ImageDraw.Draw(sheet)
for r,i in enumerate(ids):
    for c,k in enumerate("ABC"):
        x=10+c*(W+10); y=r*(H+44)+8
        d.text((x,y),f"{i}  |  {S[k]}",font=f,fill=(255,210,120))
        sheet.paste(Image.open(rf"bg_flux_style\{k}\{i}.png").convert("RGB").resize((W,H),Image.LANCZOS),(x,y+36))
out=os.environ.get("PODCAST_OUT") or os.getcwd()
sheet.save(os.path.join(out,"flux_style_test.jpg"),quality=88)
hw=os.environ.get("HWINF_CSV")
if hw and os.path.isfile(hw):
    rows=list(csv.reader(open(hw,encoding="latin-1")))
    sel=[r for r in rows[1:] if len(r)>241 and "19:27:00"<=r[1][:8]<="19:51:30"]
    print(len(sel),"hotspot",max(float(r[241]) for r in sel),"edge",max(float(r[238]) for r in sel),"memjunc",max(float(r[239]) for r in sel))
else:
    print("sensor summary skipped; set HWINF_CSV to a HWiNFO CSV export")
