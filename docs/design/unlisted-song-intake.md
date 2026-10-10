# Unlisted song intake

## Scope and decisions

An unlisted song belongs to an owner's dated Song Cart. It does not create a Song
Catalog entry. Title and pasted lyrics are required; instructions use the existing
submission comment thread. There are no per-song comments or notes.

1. From search or a draft cart, choose **Add an unlisted song**.
2. Enter title, lyrics, service date, and Call to Worship, Praise, or Worship.
3. **Save and preview** saves an ordinary cart item and prepares slides locally.
4. Review the slides and selectable formatted text, then **Mark lyrics reviewed**.
5. Review the complete cart and submit. Every unlisted item must be reviewed.
6. The Technical Team sees retained source/prepared lyrics in admin and receives
   the formatted text in the submission email.

Draft items remain editable. Changing title, section, or lyrics clears review.
The review request contains a fingerprint of the saved preview; an older browser
page cannot approve newer lyrics. Submitted items remain readable but locked.
Comments communicate later corrections without changing the submitted lyrics.
Multiple unlisted songs with the same title are allowed.

## Local preparation

The typed `prepare_lyrics` service wraps at whitespace to 45 characters and places
at most two lyric lines on each slide. Existing line/paragraph order, Unicode,
repeated words, and explicit familiar section labels are retained. Long individual
words remain whole; a word exceeding 45 characters needs correction before saving.
Label-only input and unsupported controls are rejected.
Original pasted lyrics and prepared sections are saved together; formatted text is
derived from the retained sections. The preview is an approximation of EasyWorship.

No external formatter is called. A future n8n/replacement adapter can use this
prepared-section contract; an integration pipeline, job tables, and new dependencies
are unnecessary for this slice. Drag-and-drop reordering remains separate work.

## Persistence and boundaries

Existing `SongCartItem` gains nullable catalog identity, original lyrics, prepared
sections, and review time. A source constraint distinguishes catalog and unlisted
items. Owner-scoped services lock the cart for save, review, and checkout. Rendered
routes use class-based Django views; presentation maps typed outcomes without queries.
Admin sees prepared content through the same submission read service. Migration
0003 preserves existing catalog selections with empty preparation fields.

## Verification (2026-10-10)

- 214 song-cart, account-foundation, and catalog tests plus 42 subtests passed.
- Django system check, migration drift check, TypeScript, and whitespace checks passed.
- Local PostgreSQL migration0003 applied with existing selections preserved.
- Signed-in browser walkthrough: search entry → save title/lyrics/date/section →
  slide review → edit hides stale preview → save clears review → checkout disabled
  → review revised content → submission Pending → submitted lyrics locked/readable.
- Technical Team sign-in → admin queue → detail opening Confirmed → source, prepared
  lyrics, comment, reviewer/time, and receipt/team/acknowledgement records retained.
- Local saved email body contains the prepared lyrics and submission comment; only
  dummy recipients and the console backend were exercised.
- Desktop/mobile390px layouts checked; fullscreen Tab/Shift+Tab containment and
  Escape/focus return checked. Two independent reviewers audited code/test coverage
  and captured browser evidence. Their browser surfaces were unavailable during
  this slice, so direct interaction was performed by the orchestrator.
- Real SMTP, n8n, physical devices, and screen readers were not exercised.
