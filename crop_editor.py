#!/usr/bin/env python3
"""
Crop Editor Generator
Run this script to produce crop_editor.html, then open that file in Chrome.
It lets you visually drag/zoom each person's photo and outputs the exact
photoPanX / photoPanY / photoZoom values to paste into family_db.json.
"""
import base64, json, sys
from pathlib import Path

PHOTOS_DIR = Path(__file__).parent / "photos"
DB = Path(__file__).parent / "family_db.json"
OUTPUT = Path(__file__).parent / "crop_editor.html"

MAX_DIM = 500

def load_photo_b64(filename):
    path = PHOTOS_DIR / filename
    if not path.exists():
        return None
    try:
        from PIL import Image
        import io
        img = Image.open(path).convert("RGB")
        w, h = img.size
        if w > MAX_DIM or h > MAX_DIM:
            if w >= h:
                nw, nh = MAX_DIM, round(h * MAX_DIM / w)
            else:
                nw, nh = round(w * MAX_DIM / h), MAX_DIM
            img = img.resize((nw, nh), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        with open(path, "rb") as f:
            return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()

with open(DB) as f:
    people = json.load(f)

entries = []
for person in people:
    vitals = person.get("vitals") or {}
    photo_file = vitals.get("photo", "")
    if photo_file and not photo_file.startswith("data:"):
        b64 = load_photo_b64(photo_file)
        if b64:
            entries.append({
                "id": person["id"],
                "name": person["name"],
                "photo": b64,
                "panX": vitals.get("photoPanX", 0),
                "panY": vitals.get("photoPanY", 0),
                "zoom": vitals.get("photoZoom", 1),
                "type": "vitals",
            })

    for idx, pv in (person.get("partnerVitals") or {}).items():
        pv_photo = pv.get("photo", "")
        if pv_photo and not pv_photo.startswith("data:"):
            b64 = load_photo_b64(pv_photo)
            partner_name = ""
            partners = person.get("partners") or []
            try:
                partner_name = partners[int(idx)]
            except (IndexError, ValueError):
                partner_name = f"Partner {idx}"
            if b64:
                entries.append({
                    "id": f"{person['id']}__p{idx}",
                    "name": partner_name,
                    "photo": b64,
                    "panX": pv.get("photoPanX", 0),
                    "panY": pv.get("photoPanY", 0),
                    "zoom": pv.get("photoZoom", 1),
                    "type": "partnerVitals",
                    "parentId": person["id"],
                    "partnerIdx": idx,
                })

entries_json = json.dumps(entries, separators=(",", ":"))

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Photo Crop Editor – Warshawsky Family Tree</title>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0; display: flex; height: 100vh; overflow: hidden; }}

/* Sidebar */
#sidebar {{ width: 200px; min-width: 200px; background: #16213e; border-right: 1px solid #0f3460; overflow-y: auto; display: flex; flex-direction: column; }}
#sidebar-header {{ padding: 12px 14px; font-weight: 700; font-size: 13px; background: #0f3460; color: #e2b96f; letter-spacing: 0.04em; border-bottom: 1px solid #0f3460; }}
#sidebar-count {{ font-size: 11px; color: #888; margin-top: 2px; font-weight: 400; }}
.person-btn {{ padding: 8px 14px; cursor: pointer; border: none; background: none; color: #ccc; text-align: left; width: 100%; font-size: 13px; border-bottom: 1px solid #1e2a4a; transition: background 0.1s; }}
.person-btn:hover {{ background: #1e2a4a; color: #fff; }}
.person-btn.active {{ background: #0f3460; color: #e2b96f; font-weight: 600; }}
.person-btn .btn-name {{ display: block; }}
.person-btn .btn-id {{ display: block; font-size: 10px; color: #666; margin-top: 1px; }}

/* Main */
#main {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }}
#toolbar {{ background: #16213e; border-bottom: 1px solid #0f3460; padding: 8px 14px; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }}
#toolbar h2 {{ font-size: 14px; font-weight: 700; color: #e2b96f; min-width: 140px; }}
.ctrl-group {{ display: flex; align-items: center; gap: 6px; font-size: 12px; color: #aaa; }}
.ctrl-group label {{ white-space: nowrap; }}
.ctrl-group input[type=range] {{ width: 80px; accent-color: #e2b96f; }}
.val-display {{ font-weight: 700; color: #e2b96f; min-width: 36px; font-size: 12px; font-family: monospace; }}
#reset-btn {{ padding: 4px 10px; background: #333; border: 1px solid #555; color: #ccc; border-radius: 5px; cursor: pointer; font-size: 12px; }}
#reset-btn:hover {{ background: #444; }}

/* Canvas */
#canvas-area {{ flex: 1; display: flex; align-items: center; justify-content: center; gap: 50px; overflow: hidden; padding: 16px; }}

/* Thumbnail preview */
.preview-block {{ display: flex; flex-direction: column; align-items: center; gap: 8px; flex-shrink: 0; }}
.preview-label {{ font-size: 10px; color: #888; text-transform: uppercase; letter-spacing: 0.08em; }}
#thumb-wrap {{ width: 112px; height: 112px; border-radius: 50%; overflow: hidden; border: 3px solid #e2b96f; position: relative; background: #222; flex-shrink: 0; }}
#thumb-img {{ width: 112px; height: 112px; object-fit: cover; position: absolute; top: 0; left: 0; transform-origin: center center; }}

/* Full-photo editor — shows entire photo, circle is an overlay */
#editor-block {{ display: flex; flex-direction: column; align-items: center; gap: 8px; flex: 1; min-width: 0; }}
#editor-container {{
  position: relative;
  cursor: grab;
  user-select: none;
  background: #111;
  overflow: visible;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #333;
  border-radius: 4px;
}}
#editor-container:active {{ cursor: grabbing; }}
#editor-photo {{
  display: block;
  max-width: 520px;
  max-height: 480px;
  object-fit: contain;
  position: relative;
  transform-origin: center center;
  pointer-events: none;
  user-select: none;
  -webkit-user-drag: none;
}}
/* SVG overlay drawn on top of photo */
#editor-svg {{
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 100%;
  pointer-events: none;
}}

/* Output */
#output-area {{ background: #16213e; border-top: 1px solid #0f3460; padding: 10px 14px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
#json-out {{ font-family: monospace; font-size: 12px; background: #0d1b2a; color: #7ec8e3; padding: 7px 10px; border-radius: 5px; flex: 1; border: 1px solid #0f3460; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
#copy-btn {{ padding: 6px 14px; background: #e2b96f; color: #1a1a2e; border: none; border-radius: 5px; cursor: pointer; font-weight: 700; font-size: 12px; white-space: nowrap; }}
#copy-btn:hover {{ background: #f0cc88; }}
#copy-btn.copied {{ background: #4caf50; color: #fff; }}
#instructions {{ background: #0f1829; border-top: 1px solid #0f3460; padding: 6px 14px; font-size: 11px; color: #555; text-align: center; }}
</style>
</head>
<body>

<div id="sidebar">
  <div id="sidebar-header">
    👤 People with Photos
    <div id="sidebar-count"></div>
  </div>
  <div id="person-list"></div>
</div>

<div id="main">
  <div id="toolbar">
    <h2 id="person-name">Select a person →</h2>
    <div class="ctrl-group">
      <label>Zoom</label>
      <input type="range" id="zoom-slider" min="0.5" max="4" step="0.01" value="1">
      <span class="val-display" id="zoom-val">1.00</span>
    </div>
    <div class="ctrl-group">
      <label>Pan X</label>
      <input type="range" id="panx-slider" min="-220" max="220" step="1" value="0">
      <span class="val-display" id="panx-val">0</span>
    </div>
    <div class="ctrl-group">
      <label>Pan Y</label>
      <input type="range" id="pany-slider" min="-220" max="220" step="1" value="0">
      <span class="val-display" id="pany-val">0</span>
    </div>
    <button id="reset-btn">Reset</button>
  </div>

  <div id="canvas-area">
    <div class="preview-block">
      <div class="preview-label">Live thumbnail</div>
      <div id="thumb-wrap"><img id="thumb-img" src="" alt=""></div>
      <div class="preview-label" style="margin-top:4px">112px circle</div>
    </div>

    <div id="editor-block">
      <div class="preview-label">Full photo — drag to reposition · scroll to zoom · circle shows crop</div>
      <div id="editor-container">
        <img id="editor-photo" src="" alt="">
        <svg id="editor-svg" xmlns="http://www.w3.org/2000/svg"></svg>
      </div>
    </div>
  </div>

  <div id="output-area">
    <div id="json-out">← Select a person from the sidebar</div>
    <button id="copy-btn">Copy JSON</button>
  </div>
  <div id="instructions">Drag the photo to reposition · Scroll to zoom · The gold circle shows exactly what the site thumbnail will look like · Copy JSON and paste into family_db.json</div>
</div>

<script>
const ENTRIES = {entries_json};
const REF = 220;   // reference frame size (pixels) stored in DB
const THUMB = 112; // rendered thumbnail size on site

let current = null;
let panX = 0, panY = 0, zoom = 1;

// Build sidebar
const list = document.getElementById('person-list');
document.getElementById('sidebar-count').textContent = ENTRIES.length + ' people';
ENTRIES.forEach((e, i) => {{
  const btn = document.createElement('button');
  btn.className = 'person-btn';
  btn.innerHTML = `<span class="btn-name">${{e.name}}</span><span class="btn-id">${{e.id}}</span>`;
  btn.addEventListener('click', () => selectEntry(i));
  list.appendChild(btn);
}});

const editorPhoto = document.getElementById('editor-photo');
const editorSvg = document.getElementById('editor-svg');
const thumbImg = document.getElementById('thumb-img');

function selectEntry(i) {{
  current = ENTRIES[i];
  panX = current.panX || 0;
  panY = current.panY || 0;
  zoom = current.zoom || 1;

  document.querySelectorAll('.person-btn').forEach((b, j) => b.classList.toggle('active', j === i));
  document.getElementById('person-name').textContent = current.name;

  // Load photo — wait for natural size
  editorPhoto.onload = () => {{ syncSliders(); applyTransforms(); }};
  editorPhoto.src = current.photo;
  thumbImg.src = current.photo;

  syncSliders();
  applyTransforms();
  updateOutput();
}}

function syncSliders() {{
  document.getElementById('zoom-slider').value = zoom;
  document.getElementById('panx-slider').value = panX;
  document.getElementById('pany-slider').value = panY;
  document.getElementById('zoom-val').textContent = zoom.toFixed(2);
  document.getElementById('panx-val').textContent = Math.round(panX);
  document.getElementById('pany-val').textContent = Math.round(panY);
}}

function applyTransforms() {{
  // --- Thumbnail (112px) ---
  const ratio = THUMB / REF;
  thumbImg.style.transform = `translate(${{panX * ratio}}px, ${{panY * ratio}}px) scale(${{zoom}})`;
  thumbImg.style.transformOrigin = 'center center';

  // --- Editor overlay ---
  // The editor shows the full photo. We need to figure out where the
  // 220px reference circle maps to in the displayed photo coordinates.
  const natW = editorPhoto.naturalWidth || 1;
  const natH = editorPhoto.naturalHeight || 1;
  const dispW = editorPhoto.offsetWidth || editorPhoto.clientWidth || 300;
  const dispH = editorPhoto.offsetHeight || editorPhoto.clientHeight || 300;

  // Scale from natural pixels to display pixels
  // (object-fit: contain so the photo is letterboxed)
  const scaleToFit = Math.min(dispW / natW, dispH / natH);
  // rendered photo dimensions inside the container
  const rendW = natW * scaleToFit;
  const rendH = natH * scaleToFit;

  // The REF frame is applied as if the photo is rendered at 500px (MAX_DIM),
  // but actually panX/panY/zoom are applied at the THUMB size scaled from REF.
  // The site renders the thumb at 112px with the photo filling 112x112 (object-fit:cover).
  // Pan is: translate(panX * (112/220), panY * (112/220)) on a 112x112 clipped square.
  // So the circle in the editor represents the 220px REF frame at display scale.

  // Center of the displayed photo in container coords
  const cx = dispW / 2;
  const cy = dispH / 2;

  // The REF frame (220px) maps to display pixels via:
  // display_px = REF * (dispW / natW) IF the photo fills by width,
  // or REF * (dispH / natH) if fills by height.
  // Since object-fit:contain, scale = scaleToFit.
  // But the thumbnail uses object-fit:cover at 112px, meaning the image is
  // scaled so its SHORTER side = 112px.
  // The crop ref frame (220px) is the size of the thumb container before cropping.
  // So the circle in editor-display-px = REF * scaleToFit... but we need to map
  // from the natural image's coordinate space.

  // Simpler: the circle radius in display pixels equals REF/2 * scaleToFit
  // (since REF maps to however many display pixels cover the natural image).
  // But cover-scale vs contain-scale differ. Use contain here for the full-photo editor.
  const circleR = (REF / 2) * scaleToFit;

  // Pan offset in display pixels: panX stored in REF coords → scale by scaleToFit
  const dispPanX = panX * scaleToFit;
  const dispPanY = panY * scaleToFit;

  // Circle center = image center + pan
  const circleX = cx + dispPanX;
  const circleY = cy + dispPanY;

  // Draw SVG: dark mask outside circle, bright circle border
  editorSvg.innerHTML = `
    <defs>
      <mask id="hole">
        <rect width="100%" height="100%" fill="white"/>
        <circle cx="${{circleX}}" cy="${{circleY}}" r="${{circleR}}" fill="black"/>
      </mask>
    </defs>
    <rect width="100%" height="100%" fill="rgba(0,0,0,0.55)" mask="url(#hole)"/>
    <circle cx="${{circleX}}" cy="${{circleY}}" r="${{circleR}}"
      fill="none" stroke="#e2b96f" stroke-width="2" stroke-dasharray="6 3"/>
    <circle cx="${{circleX}}" cy="${{circleY}}" r="3" fill="#e2b96f"/>
  `;
}}

function updateOutput() {{
  if (!current) return;
  const px = Math.round(panX), py = Math.round(panY), z = parseFloat(zoom.toFixed(2));
  const fields = [];
  if (px !== 0) fields.push(`"photoPanX": ${{px}}`);
  if (py !== 0) fields.push(`"photoPanY": ${{py}}`);
  if (z !== 1) fields.push(`"photoZoom": ${{z}}`);
  document.getElementById('json-out').textContent =
    fields.length ? fields.join(', ') : '(no crop needed — already centered)';
}}

// Sliders
document.getElementById('zoom-slider').addEventListener('input', e => {{
  zoom = parseFloat(e.target.value);
  document.getElementById('zoom-val').textContent = zoom.toFixed(2);
  applyTransforms(); updateOutput();
}});
document.getElementById('panx-slider').addEventListener('input', e => {{
  panX = parseFloat(e.target.value);
  document.getElementById('panx-val').textContent = Math.round(panX);
  applyTransforms(); updateOutput();
}});
document.getElementById('pany-slider').addEventListener('input', e => {{
  panY = parseFloat(e.target.value);
  document.getElementById('pany-val').textContent = Math.round(panY);
  applyTransforms(); updateOutput();
}});
document.getElementById('reset-btn').addEventListener('click', () => {{
  panX = 0; panY = 0; zoom = 1;
  syncSliders(); applyTransforms(); updateOutput();
}});

// Drag to pan (drag the photo, circle moves with it)
const container = document.getElementById('editor-container');
let dragging = false, dsx, dsy, dpx, dpy;
container.addEventListener('mousedown', e => {{
  if (!current) return;
  dragging = true;
  dsx = e.clientX; dsy = e.clientY; dpx = panX; dpy = panY;
  e.preventDefault();
}});
window.addEventListener('mousemove', e => {{
  if (!dragging) return;
  // Map mouse delta from display pixels back to REF coords
  const dispW = editorPhoto.offsetWidth || 300;
  const natW = editorPhoto.naturalWidth || 1;
  const natH = editorPhoto.naturalHeight || 1;
  const dispH = editorPhoto.offsetHeight || 300;
  const scaleToFit = Math.min(dispW / natW, dispH / natH);
  panX = dpx + (e.clientX - dsx) / scaleToFit;
  panY = dpy + (e.clientY - dsy) / scaleToFit;
  panX = Math.max(-220, Math.min(220, panX));
  panY = Math.max(-220, Math.min(220, panY));
  syncSliders(); applyTransforms(); updateOutput();
}});
window.addEventListener('mouseup', () => {{ dragging = false; }});

// Scroll to zoom
container.addEventListener('wheel', e => {{
  if (!current) return;
  e.preventDefault();
  zoom = Math.max(0.5, Math.min(4, zoom * (e.deltaY < 0 ? 1.08 : 0.93)));
  syncSliders(); applyTransforms(); updateOutput();
}}, {{ passive: false }});

// Redraw on window resize
window.addEventListener('resize', () => {{ if (current) applyTransforms(); }});

// Copy button
document.getElementById('copy-btn').addEventListener('click', () => {{
  const text = document.getElementById('json-out').textContent;
  navigator.clipboard.writeText(text).then(() => {{
    const btn = document.getElementById('copy-btn');
    btn.textContent = '✓ Copied!';
    btn.classList.add('copied');
    setTimeout(() => {{ btn.textContent = 'Copy JSON'; btn.classList.remove('copied'); }}, 1800);
  }});
}});
</script>
</body>
</html>
"""

with open(OUTPUT, "w") as f:
    f.write(html)

print(f"Done! Open this file in Chrome:")
print(f"  {OUTPUT}")
print(f"  ({len(entries)} people with photos)")
