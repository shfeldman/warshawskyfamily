#!/usr/bin/env python3
"""
Encrypt index.html with a password using AES-256-CBC + PBKDF2.
Produces a self-contained password-gate HTML page.

Compatible with StatiCrypt's encryption algorithm so the same
approach can be verified independently.

Usage:
    python3 encrypt.py                  # uses PASSWORD env var or prompts
    python3 encrypt.py --password XXXX  # explicit password
    python3 encrypt.py --input data-viz/index.html --title "Family Data Visualizations" \
        --url https://warshawskyfamily.com/data-viz/   # gate a secondary page
"""

import argparse
import base64
import hashlib
import io
import json
import os
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("ERROR: pip3 install cryptography", file=sys.stderr)
    sys.exit(1)

DEFAULT_INPUT = Path(__file__).parent / "index.html"
DEFAULT_TITLE = "Warshawsky Family Tree"
DEFAULT_URL   = "https://warshawskyfamily.com/"

PBKDF2_ITERATIONS = 200_000
SALT_BYTES        = 32
IV_BYTES          = 16

# ── Password prompt page (what the visitor sees) ────────────────────────────
GATE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>__GATE_TITLE__</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: Georgia, 'Times New Roman', serif;
    background: #f5f0e8;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    gap: 1.5rem;
  }
  .card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.12);
    padding: 2.5rem 3rem;
    max-width: 420px;
    width: 100%;
    text-align: center;
  }
  .founders-img {
    width: 120px;
    height: 120px;
    border-radius: 50%;
    object-fit: cover;
    margin-bottom: 1.2rem;
    border: 3px solid #c8b06a;
  }
  h1 {
    font-size: 1.5rem;
    color: #2c1810;
    margin-bottom: 0.3rem;
  }
  .subtitle {
    font-size: 0.95rem;
    color: #7a6a55;
    margin-bottom: 2rem;
  }
  label {
    display: block;
    text-align: left;
    font-size: 0.9rem;
    color: #4a3f33;
    margin-bottom: 0.4rem;
    font-weight: 600;
  }
  .pwd-wrap {
    position: relative;
    margin-bottom: 1rem;
  }
  .pwd-wrap input {
    width: 100%;
    padding: 0.75rem 3rem 0.75rem 1rem;
    font-size: 1.1rem;
    border: 2px solid #d4c5a9;
    border-radius: 8px;
    background: #faf8f4;
    color: #2c1810;
    outline: none;
    transition: border-color 0.2s;
  }
  .pwd-wrap input:focus { border-color: #8a6d1f; }
  .eye-btn {
    position: absolute;
    right: 0.75rem;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    padding: 0.25rem;
    cursor: pointer;
    color: #8a7a65;
    width: auto;
    font-size: 1.1rem;
    line-height: 1;
  }
  .eye-btn:hover { color: #4a3f33; background: none; }
  .remember-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1.2rem;
    text-align: left;
  }
  .remember-row input { width: auto; margin: 0; }
  .remember-row label { margin: 0; font-weight: 400; color: #7a6a55; }
  button {
    width: 100%;
    padding: 0.85rem;
    font-size: 1.05rem;
    font-family: inherit;
    background: #8a6d1f;
    color: #fff;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
    letter-spacing: 0.03em;
    transition: background 0.2s;
  }
  button:hover { background: #6e5618; }
  .hint {
    margin-top: 1.5rem;
    font-size: 0.78rem;
    color: #b0a090;
  }
  .qr-card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.12);
    padding: 1.2rem 2rem;
    max-width: 420px;
    width: 100%;
    text-align: center;
    display: flex;
    align-items: center;
    gap: 1.2rem;
  }
  .qr-card svg { flex-shrink: 0; }
  .qr-text { text-align: left; }
  .qr-text strong { display: block; font-size: 0.9rem; color: #2c1810; margin-bottom: 0.2rem; }
  .qr-text span { font-size: 0.78rem; color: #7a6a55; }
</style>
</head>
<body>
<div class="card">
  <h1>__GATE_TITLE__</h1>
  <p class="subtitle">Members only &mdash; please enter the family password</p>
  <label for="pwd">Password</label>
  <div class="pwd-wrap">
    <input type="text" id="pwd" placeholder="Enter family password" autocomplete="off" spellcheck="false" autocorrect="off" autocapitalize="off">
    <button class="eye-btn" id="eye-btn" type="button" aria-label="Show password" title="Show/hide password">&#128065;</button>
  </div>
  <div class="remember-row">
    <input type="checkbox" id="remember" checked>
    <label for="remember">Remember me on this device</label>
  </div>
  <button id="enter-btn" type="button">Enter Family Tree</button>
  <p class="hint">Contact a family member if you need the password.</p>
</div>

<div class="qr-card">
  __QR_CODE_SVG__
  <div class="qr-text">
    <strong>On a phone? Scan to open.</strong>
    <span>Point your camera at this code &mdash; no typing needed.</span>
  </div>
</div>

<script>
const ENCRYPTED = __ENCRYPTED_PAYLOAD__;
const STORAGE_KEY = 'wfc_pwd';

// ── Password input: masked with show/hide toggle ──────────────────────────
let realPwd = '';
let peekTimer = null;
let showingPwd = false;
const DOT = '•';

function renderPwd() {
  const el = document.getElementById('pwd');
  if (showingPwd) {
    el.value = realPwd;
  } else {
    el.value = DOT.repeat(realPwd.length);
  }
}

function showPeek() {
  if (showingPwd) { renderPwd(); return; }
  clearTimeout(peekTimer);
  const el = document.getElementById('pwd');
  el.value = DOT.repeat(Math.max(0, realPwd.length - 1)) + realPwd.slice(-1);
  peekTimer = setTimeout(renderPwd, 800);
}

document.getElementById('eye-btn').addEventListener('mousedown', function(e) {
  e.preventDefault(); // keep focus on the input
});
document.getElementById('eye-btn').addEventListener('click', function() {
  showingPwd = !showingPwd;
  this.textContent = showingPwd ? '✖' : '👁';
  this.setAttribute('aria-label', showingPwd ? 'Hide password' : 'Show password');
  clearTimeout(peekTimer);
  renderPwd();
  document.getElementById('pwd').focus();
});

document.getElementById('pwd').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') return;
  if (e.ctrlKey || e.metaKey) {
    if (e.key === 'a') { realPwd = ''; renderPwd(); e.preventDefault(); }
    else if (e.key === 'v') {
      navigator.clipboard && navigator.clipboard.readText().then(text => {
        realPwd += text.trim();
        showPeek();
      }).catch(() => {});
      e.preventDefault();
    }
    return;
  }
  if (e.key === 'Backspace') { realPwd = realPwd.slice(0, -1); renderPwd(); e.preventDefault(); }
  else if (e.key === 'Delete') { realPwd = ''; renderPwd(); e.preventDefault(); }
  else if (e.key.length === 1) { realPwd += e.key; showPeek(); e.preventDefault(); }
});

// ── Core decrypt — password is always lowercased ──────────────────────────
function hexToBytes(hex) {
  const b = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) b[i/2] = parseInt(hex.substr(i,2),16);
  return b;
}

async function tryDecrypt(pwd) {
  pwd = pwd.trim().toLowerCase();
  const { ct, salt, iv } = ENCRYPTED;
  const enc = new TextEncoder();
  const mat = await crypto.subtle.importKey('raw', enc.encode(pwd), {name:'PBKDF2'}, false, ['deriveKey']);
  const key = await crypto.subtle.deriveKey(
    {name:'PBKDF2', salt:hexToBytes(salt), iterations:200000, hash:'SHA-256'},
    mat, {name:'AES-CBC',length:256}, false, ['decrypt']
  );
  try {
    const plain = await crypto.subtle.decrypt({name:'AES-CBC',iv:hexToBytes(iv)}, key, hexToBytes(ct));
    const text = new TextDecoder().decode(plain);
    if (text.includes('<!DOCTYPE') || text.includes('<html')) return text;
  } catch(e) {}
  return null;
}

// ── Render decrypted page ─────────────────────────────────────────────────
function render(html) {
  document.body.innerHTML = '';
  document.documentElement.style.cssText = 'margin:0;padding:0;overflow:hidden;height:100%;';
  document.body.style.cssText = 'margin:0;padding:0;overflow:hidden;height:100%;';
  const iframe = document.createElement('iframe');
  iframe.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;border:none;';
  iframe.srcdoc = html;
  document.body.appendChild(iframe);
}

function showLoading() {
  document.body.innerHTML = '<div style="font-family:Georgia,serif;display:flex;align-items:center;justify-content:center;min-height:100vh;font-size:1.2rem;color:#8a6d1f;">Opening family tree…</div>';
}

// ── Unlock from typed password ────────────────────────────────────────────
async function unlock() {
  const pwd = realPwd.trim();
  if (!pwd) return;
  showLoading();
  const html = await tryDecrypt(pwd);
  if (html) {
    const remember = document.getElementById('remember') && document.getElementById('remember').checked;
    if (remember) {
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify({pwd: pwd.toLowerCase(), exp: Date.now()+30*24*60*60*1000})); } catch(e){}
    }
    render(html);
  } else {
    location.reload();
  }
}

document.getElementById('pwd').addEventListener('keydown', e => { if(e.key==='Enter') unlock(); }, true);
document.getElementById('enter-btn').addEventListener('click', unlock);

// ── URL bypass runs FIRST ─────────────────────────────────────────────────
(function() {
  const hash = window.location.hash;
  if (!hash.startsWith('#open:')) return;
  const bypass = decodeURIComponent(hash.slice(6));
  if (!bypass) return;
  showLoading();
  tryDecrypt(bypass).then(html => {
    if (html) {
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify({pwd: bypass.toLowerCase(), exp: Date.now()+30*24*60*60*1000})); } catch(e) {}
      render(html);
    } else {
      history.replaceState(null, '', location.pathname);
      location.reload();
    }
  }).catch(() => { history.replaceState(null, '', location.pathname); location.reload(); });
})();

// ── Remember-me ───────────────────────────────────────────────────────────
(function() {
  if (window.location.hash.startsWith('#open:')) return;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return;
    const {pwd, exp} = JSON.parse(saved);
    if (exp && Date.now() > exp) { localStorage.removeItem(STORAGE_KEY); return; }
    showLoading();
    tryDecrypt(pwd).then(html => {
      if (html) render(html);
      else { localStorage.removeItem(STORAGE_KEY); location.reload(); }
    }).catch(() => { localStorage.removeItem(STORAGE_KEY); location.reload(); });
  } catch(e) {}
})();
</script>
</body>
</html>
"""


def pkcs7_pad(data: bytes, block_size: int = 16) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)


def encrypt_html(plaintext: bytes, password: str):
    salt = os.urandom(SALT_BYTES)
    iv   = os.urandom(IV_BYTES)

    key = hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS, dklen=32
    )

    padded = pkcs7_pad(plaintext)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    enc    = cipher.encryptor()
    ct     = enc.update(padded) + enc.finalize()

    return {
        'salt': salt.hex(),
        'iv':   iv.hex(),
        'ct':   ct.hex(),
    }


def make_qr_svg(url: str, size: int = 120) -> str:
    """Generate a QR code as an inline SVG string."""
    try:
        import qrcode
        import qrcode.image.svg as qrsvg
        factory = qrsvg.SvgPathImage
        qr = qrcode.make(url, image_factory=factory, box_size=4, border=2)
        buf = io.BytesIO()
        qr.save(buf)
        svg = buf.getvalue().decode('utf-8')
        # Strip XML declaration and set a fixed size
        svg = svg[svg.index('<svg'):]
        svg = svg.replace('height="', f'height="{size}" data-orig-height="')
        svg = svg.replace('width="', f'width="{size}" data-orig-width="')
        return svg
    except ImportError:
        return '<div style="font-size:0.75rem;color:#b0a090;">QR unavailable</div>'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--password', default=None)
    parser.add_argument('--input', default=str(DEFAULT_INPUT),
                        help='HTML file to encrypt (default: index.html)')
    parser.add_argument('--output', default=None,
                        help='Where to write the gate page (default: same as --input)')
    parser.add_argument('--title', default=DEFAULT_TITLE,
                        help='Title shown on the password gate')
    parser.add_argument('--url', default=DEFAULT_URL,
                        help='Public URL of the page, used for the QR code')
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path

    password = args.password or os.environ.get('WFC_PASSWORD') or None
    if not password:
        pw_file = Path(__file__).parent / '.wfc_password'
        if pw_file.exists():
            password = pw_file.read_text().strip()
    if not password:
        import getpass
        password = getpass.getpass('Family password: ')

    # Always encrypt with lowercase so the gate JS can accept any case
    password = password.lower()

    if not input_path.exists():
        print(f"ERROR: {input_path} not found — run build.py first.", file=sys.stderr)
        sys.exit(1)

    plaintext = input_path.read_bytes()
    print(f"Encrypting {input_path} ({len(plaintext)/1024:.1f} KB)...")
    payload = encrypt_html(plaintext, password)

    bypass_url = f'{args.url}#open:{password}'
    qr_svg = make_qr_svg(bypass_url)
    gate = GATE_HTML.replace('__ENCRYPTED_PAYLOAD__', json.dumps(payload))
    gate = gate.replace('__QR_CODE_SVG__', qr_svg)
    gate = gate.replace('__GATE_TITLE__', args.title)
    output_path.write_text(gate, encoding='utf-8')
    print(f"Protected page written: {output_path} ({output_path.stat().st_size/1024:.1f} KB)")
    print("Password gate is active.")


if __name__ == '__main__':
    main()
