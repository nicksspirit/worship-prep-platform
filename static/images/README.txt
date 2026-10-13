Right-sized renditions of static/rccgcm_logo.png (500x500 original, kept for the admin).
The header shows the logo in a ~52px box scaled 1.3x, so 96px (1x) and 192px (2x) cover it.

  *.webp  cwebp -q 90 -alpha_q 100 -m 6  (visually lossless)
  *.png   Pillow LANCZOS resize + 256-colour palette quantisation (fallback for browsers without WebP)

Filenames end in the first 12 hex characters of the file's SHA-256, which makes
WhiteNoise serve them as immutable (see WHITENOISE_IMMUTABLE_FILE_TEST in
backend/settings/components/storage.py). Never edit a file in place: add the new file
with its new hash and update client/Layout.tsx.
