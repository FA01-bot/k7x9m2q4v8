from pathlib import Path
import os, html, re, shutil, json, hashlib
from PIL import Image, ImageOps
import qrcode

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

def natural_key(path):
    text = path.as_posix().lower()
    return [
        int(part) if part.isdigit() else part
        for part in re.split(r"(\d+)", text)
    ]

def collect(folder):
    if not folder.exists():
        return []

    files = [
        f for f in folder.rglob("*")
        if f.is_file() and f.suffix.lower() in image_exts
    ]
    return sorted(files, key=natural_key)

portrait_sources = collect(site / "portrait") + collect(site / "images" / "portrait")
landscape_sources = collect(site / "landscape") + collect(site / "images" / "landscape")

if not portrait_sources:
    raise SystemExit(
        "No portrait images found. Put at least one image in "
        "site/portrait/ or site/images/portrait/."
    )

def optimize_group(files, group):
    out_dir = target / "media" / group
    out_dir.mkdir(parents=True, exist_ok=True)

    max_size = (1200, 2000) if group == "portrait" else (2000, 1200)

    urls = []
    total_before = 0
    total_after = 0

    for source in files:
        raw = source.read_bytes()
        total_before += len(raw)

        digest = hashlib.sha256(raw).hexdigest()[:16]
        dest = out_dir / f"{digest}.webp"

        with Image.open(source) as im:
            im = ImageOps.exif_transpose(im)
            im.thumbnail(max_size, Image.Resampling.LANCZOS)

            if "A" in im.getbands():
                im = im.convert("RGBA")
            else:
                im = im.convert("RGB")

            im.save(
                dest,
                "WEBP",
                quality=82,
                method=6,
                optimize=True,
            )

        total_after += dest.stat().st_size
        urls.append(dest.relative_to(target).as_posix())

    before_mb = total_before / (1024 * 1024)
    after_mb = total_after / (1024 * 1024)

    print(
        f"{group}: {len(files)} image(s), "
        f"{before_mb:.2f} MB source -> {after_mb:.2f} MB deployed WebP"
    )

    return urls

portrait_images = optimize_group(portrait_sources, "portrait")

if landscape_sources:
    landscape_images = optimize_group(landscape_sources, "landscape")
else:
    landscape_images = list(portrait_images)
    print("landscape: no images; using portrait group as fallback")

manifest = {
    "portrait": portrait_images,
    "landscape": landscape_images,
}

manifest_text = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
build_id = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()[:16]

manifest_json = (
    manifest_text
    .replace("<", "\\u003c")
    .replace(">", "\\u003e")
    .replace("&", "\\u0026")
)
build_id_json = json.dumps(build_id)

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

page = page.replace("__IMAGE_MANIFEST_JSON__", manifest_json)
page = page.replace("__IMAGE_BUILD_ID_JSON__", build_id_json)
(target / "index.html").write_text(page, encoding="utf-8")

def vcard_escape(v):
    return (
        v.replace("\\","\\\\")
         .replace("\n","\\n")
         .replace(";","\\;")
         .replace(",","\\,")
    )

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

(target / "contact.vcf").write_text(
    vcf,
    encoding="utf-8",
    newline="\r\n"
)

# ------------------------------------------------------------------
# QR Code for the deployed card URL.
# This avoids loading a third-party QR service or JS library at runtime.
# ------------------------------------------------------------------
repo_full = os.environ.get("GITHUB_REPOSITORY", "").strip()
owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "").strip()

if repo_full and "/" in repo_full:
    repo_owner, repo_name = repo_full.split("/", 1)
    if not owner:
        owner = repo_owner
else:
    # Current repository fallback; GITHUB_REPOSITORY is present in Actions.
    owner = owner or "FA01-bot"
    repo_name = "k7x9m2q4v8"

card_url = f"https://{owner.lower()}.github.io/{repo_name}/{card_path}/"

qr = qrcode.QRCode(
    version=None,
    error_correction=qrcode.constants.ERROR_CORRECT_M,
    box_size=9,
    border=4,
)
qr.add_data(card_url)
qr.make(fit=True)

qr_img = qr.make_image(
    fill_color="#121728",
    back_color="#ffffff"
).convert("RGB")
qr_img.save(target / "qr.png", optimize=True)

print(f"QR generated for: {card_url}")

(out / "robots.txt").write_text(
    "User-agent: *\nDisallow: /\n",
    encoding="utf-8"
)

root_page = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive,nosnippet">
<title>404</title><style>
html,body{height:100%;margin:0;background:#121728;color:#cbd5e1;font-family:system-ui,sans-serif}
body{display:grid;place-items:center}.x{text-align:center}h1{font-size:64px;margin:0}p{opacity:.72}
</style></head><body><div class="x"><h1>404</h1><p>Page not found.</p></div></body></html>"""

(out / "index.html").write_text(root_page, encoding="utf-8")
(out / "404.html").write_text(root_page, encoding="utf-8")
(out / ".nojekyll").write_text("", encoding="utf-8")

print(
    f"Pages artifact built successfully. "
    f"Portrait: {len(portrait_images)}, landscape: {len(landscape_images)}, "
    f"build id: {build_id}"
)
