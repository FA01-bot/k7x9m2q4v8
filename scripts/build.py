from pathlib import Path
import os, html, re, shutil, json

required = [
    "CARD_PATH","CARD_NAME","CARD_PHONE","CARD_EMAIL",
    "CARD_IG_URL","CARD_LINE_URL","CARD_DISCORD_URL",
]

missing = [k for k in required if not os.environ.get(k)]
if missing:
    raise SystemExit("Missing required GitHub Secrets: " + ", ".join(missing))

card_path = os.environ["CARD_PATH"].strip().strip("/")
if not re.fullmatch(r"[A-Za-z0-9_-]{12,80}", card_path):
    raise SystemExit("CARD_PATH must be 12-80 characters using only letters, numbers, _ or -.")

site = Path("site")
out = Path("_site")
target = out / card_path

if out.exists():
    shutil.rmtree(out)
target.mkdir(parents=True)

image_exts = {".jpg", ".jpeg", ".png", ".webp", ".avif"}

def collect(folder):
    if not folder.exists():
        return []
    return [
        f.relative_to(site).as_posix()
        for f in sorted(folder.rglob("*"))
        if f.is_file() and f.suffix.lower() in image_exts
    ]

portrait_dirs = [site / "portrait", site / "images" / "portrait"]
landscape_dirs = [site / "landscape", site / "images" / "landscape"]

portrait_images = sum((collect(p) for p in portrait_dirs), [])
landscape_images = sum((collect(p) for p in landscape_dirs), [])

for folder in [site / "portrait", site / "landscape", site / "images"]:
    if folder.exists():
        shutil.copytree(folder, target / folder.relative_to(site), dirs_exist_ok=True)

fallback = site / "asset-01.jpg"
if fallback.exists():
    shutil.copy2(fallback, target / "asset-01.jpg")

if not portrait_images:
    if fallback.exists():
        portrait_images = ["asset-01.jpg"]
    else:
        raise SystemExit(
            "No portrait images found. Put at least one image in "
            "site/portrait/ or site/images/portrait/."
        )

if not landscape_images:
    landscape_images = list(portrait_images)

manifest = {"portrait": portrait_images, "landscape": landscape_images}
(target / "image-manifest.js").write_text(
    "window.CARD_IMAGES = " +
    json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) +
    ";\n",
    encoding="utf-8",
)

vals = {
    "__CARD_NAME__": html.escape(os.environ["CARD_NAME"], quote=True),
    "__CARD_PHONE__": html.escape(os.environ["CARD_PHONE"], quote=True),
    "__CARD_EMAIL__": html.escape(os.environ["CARD_EMAIL"], quote=True),
    "__CARD_IG_URL__": html.escape(os.environ["CARD_IG_URL"], quote=True),
    "__CARD_LINE_URL__": html.escape(os.environ["CARD_LINE_URL"], quote=True),
    "__CARD_DISCORD_URL__": html.escape(os.environ["CARD_DISCORD_URL"], quote=True),
}

page = (site / "index.template.html").read_text(encoding="utf-8")
for token, value in vals.items():
    page = page.replace(token, value)
(target / "index.html").write_text(page, encoding="utf-8")

def vcard_escape(v):
    return v.replace("\\","\\\\").replace("\n","\\n").replace(";","\\;").replace(",","\\,")

vcf_vals = {
    "__CARD_NAME__": vcard_escape(os.environ["CARD_NAME"]),
    "__CARD_PHONE__": vcard_escape(os.environ["CARD_PHONE"]),
    "__CARD_EMAIL__": vcard_escape(os.environ["CARD_EMAIL"]),
    "__CARD_IG_URL__": vcard_escape(os.environ["CARD_IG_URL"]),
    "__CARD_LINE_URL__": vcard_escape(os.environ["CARD_LINE_URL"]),
    "__CARD_DISCORD_URL__": vcard_escape(os.environ["CARD_DISCORD_URL"]),
}

vcf = (site / "contact.template.vcf").read_text(encoding="utf-8")
for token, value in vcf_vals.items():
    vcf = vcf.replace(token, value)
(target / "contact.vcf").write_text(vcf, encoding="utf-8", newline="\r\n")

(out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")

root_page = '''<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive,nosnippet">
<title>404</title><style>
html,body{height:100%;margin:0;background:#121728;color:#cbd5e1;font-family:system-ui,sans-serif}
body{display:grid;place-items:center}.x{text-align:center}h1{font-size:64px;margin:0}p{opacity:.72}
</style></head><body><div class="x"><h1>404</h1><p>Page not found.</p></div></body></html>'''

(out / "index.html").write_text(root_page, encoding="utf-8")
(out / "404.html").write_text(root_page, encoding="utf-8")
(out / ".nojekyll").write_text("", encoding="utf-8")

print(f"Pages artifact built successfully. Portrait images: {len(portrait_images)}, landscape images: {len(landscape_images)}")
