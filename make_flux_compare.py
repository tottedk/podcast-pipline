from PIL import Image, ImageDraw, ImageFont
import os
ids=["c01a","c02c","c03a","c05b","c08c"]; D=os.environ.get("PODCAST_OUT") or os.getcwd()
f=ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf",40)
outs=[]
for i in ids:
    L=Image.open(rf"bg_pw1\{i}.png").convert("RGB"); R=Image.open(rf"bg_flux_test\{i}.png").convert("RGB")
    c=Image.new("RGB",(3860,1160),(20,20,20)); c.paste(L,(0,80)); c.paste(R,(1940,80)); d=ImageDraw.Draw(c)
    d.text((20,18),f"{i}  SDXL base 1.0 (30 steps, cfg 6.5)",font=f,fill=(255,200,90)); d.text((1960,18),f"{i}  FLUX.1 schnell (4 steps, fp8 storage)",font=f,fill=(120,220,255))
    p=os.path.join(D,f"flux_vs_sdxl_{i}.jpg"); c.save(p,quality=90); outs.append(c)
w=1930; sheet=Image.new("RGB",(w,len(outs)*580),(20,20,20))
for k,c in enumerate(outs): sheet.paste(c.resize((w,580),Image.LANCZOS),(0,k*580))
sheet.save(os.path.join(D,"flux_vs_sdxl_compare.jpg"),quality=85)
print(os.path.getsize(os.path.join(D,"flux_vs_sdxl_compare.jpg")))
