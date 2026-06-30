#!/usr/bin/env python3
"""
Encrypt index.html with a password using AES-256-CBC + PBKDF2.
Produces a self-contained password-gate HTML page.

Compatible with StatiCrypt's encryption algorithm so the same
approach can be verified independently.

Usage:
    python3 encrypt.py                  # uses PASSWORD env var or prompts
    python3 encrypt.py --password XXXX  # explicit password
"""

import argparse
import base64
import hashlib
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

INPUT  = Path(__file__).parent / "index.html"
OUTPUT = Path(__file__).parent / "index.html"

PBKDF2_ITERATIONS = 600_000
SALT_BYTES        = 32
IV_BYTES          = 16

# ── Password prompt page (what the visitor sees) ────────────────────────────
GATE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Warshawsky Family Tree</title>
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
  input[type="password"] {
    width: 100%;
    padding: 0.75rem 1rem;
    font-size: 1.1rem;
    border: 2px solid #d4c5a9;
    border-radius: 8px;
    margin-bottom: 1rem;
    background: #faf8f4;
    color: #2c1810;
    outline: none;
    transition: border-color 0.2s;
  }
  input[type="password"]:focus { border-color: #8a6d1f; }
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
  .error {
    color: #c0392b;
    font-size: 0.9rem;
    margin-top: 0.8rem;
    display: none;
  }
  .hint {
    margin-top: 1.5rem;
    font-size: 0.78rem;
    color: #b0a090;
  }
</style>
</head>
<body>
<div class="card">
  <h1>Warshawsky Family Tree</h1>
  <p class="subtitle">Members only &mdash; please enter the family password</p>
  <label for="pwd">Password</label>
  <input type="password" id="pwd" placeholder="Enter family password" autocomplete="current-password">
  <div class="remember-row">
    <input type="checkbox" id="remember" checked>
    <label for="remember">Remember me on this device</label>
  </div>
  <button onclick="unlock()">Enter Family Tree</button>
  <div class="error" id="err">Incorrect password &mdash; please try again.</div>
  <p class="hint">Contact a family member if you need the password.</p>
</div>

<script>
const ENCRYPTED = __ENCRYPTED_PAYLOAD__;
const STORAGE_KEY = 'wfc_session';

async function unlock() {
  const pwd = document.getElementById('pwd').value;
  if (!pwd) return;
  document.querySelector('button').textContent = 'Unlocking…';
  try {
    const { ct, salt, iv } = ENCRYPTED;
    const html = await decrypt(ct, salt, iv, pwd);
    if (html) {
      if (document.getElementById('remember').checked) {
        const exp = Date.now() + 30 * 24 * 60 * 60 * 1000; // 30 days
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ ct, salt, iv, exp }));
      }
      render(html);
    } else {
      showError();
    }
  } catch(e) {
    showError();
  }
}

function showError() {
  document.querySelector('button').textContent = 'Enter Family Tree';
  document.getElementById('err').style.display = 'block';
  document.getElementById('pwd').focus();
}

async function decrypt(ct, salt, iv, pwd) {
  if (!pwd) {
    // try stored key
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return null;
    try {
      const data = JSON.parse(stored);
      return decrypt(data.ct, data.salt, data.iv, null);
    } catch(e) { return null; }
  }
  try {
    const enc  = new TextEncoder();
    const saltBytes = hexToBytes(salt);
    const ivBytes   = hexToBytes(iv);
    const keyMaterial = await crypto.subtle.importKey(
      'raw', enc.encode(pwd), { name: 'PBKDF2' }, false, ['deriveKey']
    );
    const key = await crypto.subtle.deriveKey(
      { name: 'PBKDF2', salt: saltBytes, iterations: 600000, hash: 'SHA-256' },
      keyMaterial,
      { name: 'AES-CBC', length: 256 },
      false,
      ['decrypt']
    );
    const ctBytes = hexToBytes(ct);
    const plain = await crypto.subtle.decrypt({ name: 'AES-CBC', iv: ivBytes }, key, ctBytes);
    const text = new TextDecoder().decode(plain);
    // Basic sanity check
    if (text.includes('<html') || text.includes('<!DOCTYPE')) return text;
    return null;
  } catch(e) {
    return null;
  }
}

function hexToBytes(hex) {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2)
    bytes[i/2] = parseInt(hex.substr(i, 2), 16);
  return bytes;
}

function render(html) {
  document.open();
  document.write(html);
  document.close();
}

document.getElementById('pwd').addEventListener('keydown', e => {
  if (e.key === 'Enter') unlock();
});

// Secret URL bypass: ?open=PASSWORD skips the gate entirely
(function() {
  const params = new URLSearchParams(window.location.search);
  const bypass = params.get('open');
  if (bypass) {
    decrypt(ENCRYPTED.ct, ENCRYPTED.salt, ENCRYPTED.iv, bypass).then(html => {
      if (html) render(html);
    }).catch(() => {});
    return;
  }
})();

// Check remembered session
(function() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const { ct, salt, iv, exp } = JSON.parse(saved);
      if (!exp || Date.now() < exp) {
        decrypt(ct, salt, iv).then(html => { if (html) render(html); }).catch(() => {});
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    }
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--password', default=None)
    args = parser.parse_args()

    password = args.password or os.environ.get('WFC_PASSWORD') or None
    if not password:
        import getpass
        password = getpass.getpass('Family password: ')

    if not INPUT.exists():
        print(f"ERROR: {INPUT} not found — run build.py first.", file=sys.stderr)
        sys.exit(1)

    plaintext = INPUT.read_bytes()
    print(f"Encrypting {INPUT.name} ({len(plaintext)/1024:.1f} KB)...")
    payload = encrypt_html(plaintext, password)

    gate = GATE_HTML.replace('__ENCRYPTED_PAYLOAD__', json.dumps(payload))
    OUTPUT.write_text(gate, encoding='utf-8')
    print(f"Protected page written: {OUTPUT.name} ({OUTPUT.stat().st_size/1024:.1f} KB)")
    print("Password gate is active.")


if __name__ == '__main__':
    main()
