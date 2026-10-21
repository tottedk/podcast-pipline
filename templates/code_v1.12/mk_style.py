import json, os
S = {"A": "A dark cyber-gothic digital matte painting with soft painterly brushwork, lit by warm amber lamplight from the left against deep teal shadows, heavy atmosphere, wide cinematic shot, low angle, subtle film grain, no text or lettering anywhere.",
     "B": "A dark cinematic photograph, deep teal and cold blue tones with a single small amber light, sharp detail, wide-angle lens, low angle, volumetric fog, film grain, no text or lettering anywhere.",
     "C": "A dark cyber-gothic cinematic concept art illustration, semi-realistic with painterly texture, balanced warm amber highlights and teal shadows, moody volumetric light, wide cinematic shot, low angle, film grain, no text or lettering anywhere."}
P = [{"id": "c01a", "prompt": "The San Francisco skyline sits low along the bottom third of the frame, seen across the dark bay at night with fog rolling around its glowing towers, while a vast empty dark night sky fills the upper two thirds of the image."},
     {"id": "c03a", "prompt": "A single empty gothic throne with a crown resting on a ledger book stands small in the lower third of the frame at the far end of a vast stone hall, while high dark vaulted empty space fills the upper two thirds of the image."},
     {"id": "c05b", "prompt": "A low curved wall of countless glowing surveillance camera lenses forms a band along the bottom third of the frame, all facing one dark eye-shaped node at its centre, while empty black space fills the upper two thirds of the image."}]
for k, s in S.items():
    os.makedirs(rf"bg_flux_style\{k}", exist_ok=True)
    json.dump({"style": s, "negative": "", "images": P}, open(rf"bg_flux_style\{k}\prompts.json", "w", encoding="utf-8"), indent=1)
