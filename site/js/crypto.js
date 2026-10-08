// Mirrors exporter/encrypt.py: "FWV1" | salt16 | iv12 | AES-GCM ciphertext.
const MAGIC = [0x46, 0x57, 0x56, 0x31];
const ITERATIONS = 200000;

export async function decryptBundle(buf, passphrase) {
  const bytes = new Uint8Array(buf);
  if (!MAGIC.every((b, i) => bytes[i] === b)) throw new Error('not an encrypted bundle');
  const salt = bytes.slice(4, 20), iv = bytes.slice(20, 32), ct = bytes.slice(32);
  const enc = new TextEncoder();
  const base = await crypto.subtle.importKey('raw', enc.encode(passphrase), 'PBKDF2', false, ['deriveKey']);
  const key = await crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: ITERATIONS, hash: 'SHA-256' },
    base, { name: 'AES-GCM', length: 256 }, false, ['decrypt']);
  try {
    return await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ct);
  } catch (e) {
    throw new Error('wrong passphrase');
  }
}

/** Passphrase from the URL fragment (#k=...), never sent to the server. */
export function keyFromFragment() {
  const m = location.hash.match(/[#&]k=([^&]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}
