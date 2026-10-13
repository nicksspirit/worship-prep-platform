Self-hosted web fonts (Latin subset, WOFF2), licensed under the SIL Open Font License 1.1.
The license texts are in OFL-*.txt in this directory.

Source: Fontsource 5.3.0 builds of the official Google Fonts releases.
  cormorant-garamond-latin-400-{normal,italic}  @fontsource/cormorant-garamond
  instrument-sans-latin-wght-normal             @fontsource-variable/instrument-sans (wght axis, 400-700)
  instrument-sans-latin-400-italic              @fontsource/instrument-sans

Filenames end in the first 12 hex characters of the file's SHA-256, which makes
WhiteNoise serve them as immutable (see WHITENOISE_IMMUTABLE_FILE_TEST in
backend/settings/components/storage.py). Never edit a file in place: add the new file
with its new hash and update client/styles.css and client/Layout.tsx.
