# EasyWorship lyric section labels

## Finding

EasyWorship song sections are **not stored as a closed enum** such as Verse,
Chorus, Bridge, and Tag. In the inspected EasyWorship data, each label is
free-form text embedded in the song's RTF. The same RTF uses
`\sdparawysiwghidden` to mark label paragraphs and `\sdslidemarker` to mark
slide boundaries. `SongWords.db` has no separate label or section-type column.

The importer must therefore preserve the exact source label. It may also derive
a normalized interpretation for filtering or display, but it must not replace
the source value or reject an unfamiliar value.

## Primary evidence

1. The official EasyWorship manual says operators "type the label you want to
   use" and gives `Verse 1`, `Chorus`, and `Intro` as examples. Its label
   settings page says users can add new labels when the desired label does not
   exist and can configure label color coding and shortcut keys. This makes the
   configured label vocabulary extensible rather than fixed. Evidence:
   `/Users/nickmuoh/Downloads/EasyWorship7Manual.pdf`, PDF pages 240, 326, 331,
   and 339 (SHA-256
   `54f777a2e716dbd907dc159dbd3b2a0a58d1257cf28c937c1fe929cefc0b5c07`).
2. The authentic `SongWords.db` schema contains only `song_id`, `words`,
   `slide_uids`, `slide_layout_revisions`, and `slide_revisions`; labels are not
   stored in a relational type/label column. Evidence:
   `/Users/nickmuoh/Downloads/database_backups/20260705_090643/SongWords.db`
   (SHA-256
   `16f378d098cf106815ec67feab0b269ed623d67e28d6468848f207652f13fd39`).
3. In that database's 2,283 `word` rows, 1,194 RTF paragraphs carried
   `\sdparawysiwghidden`. Decoding those paragraphs produced 280 exact distinct
   strings (250 after case-folding), including conventional labels, numbered
   variants, punctuation/casing variants, performance directions, arbitrary
   custom text, and 12 empty labels.
4. A first-party `.ewsx` schedule preserves the same representation in its
   `resource_text.rtf`: observed exact values included `Verse 1`, `Chorus`,
   `Verse 2`, `Verse 3`, `Verse 4`, `Verse 5`, and the custom value
   `Sunday School`. Evidence:
   `/Users/nickmuoh/Downloads/Developer/Schedules/02082026.ewsx` (SHA-256
   `d33980e8fc0745ff250793fd307fa162a350379776a7673d00c9e4d42cf560c5`).

## What is fixed, configured, and observed

- **Fixed storage mechanism:** a hidden RTF paragraph stores the label as text.
- **Documented examples:** `Verse 1`, `Chorus`, and `Intro`.
- **Configured labels:** EasyWorship supports adding labels and assigning label
  shortcuts/colors. The exact default configured list was not recoverable from
  the gathered text evidence, so this note does not claim a definitive built-in
  list.
- **Numbered variants:** numbers are part of the free-form string. The corpus
  contains exact `Verse 1` through `Verse 7`, and `Chorus 1` through
  `Chorus 3`, plus casing, punctuation, continuation, and suffix variants.
- **Custom labels:** arbitrary operator-entered values are valid source data.
  The corpus contains values such as `Call & Response`, `Solo`, `Vamp`,
  `Sunday School`, repeat directions, song-specific phrases, and even text that
  appears to have been accidentally entered in the label field.

`Bridge`, `Refrain`, `Pre-Chorus`, and many other values below are confirmed as
stored labels in this corpus, but the current evidence does **not** establish
that each is a factory default. `Ending`, `Introduction`, `Misc`, and `Tag`
were not observed in this corpus; absence here does not mean EasyWorship
forbids them.

## Exact labels observed in the newest backup

The following is the complete set of 280 exact decoded strings from the
`20260705_090643` backup, sorted case-insensitively. The first entry, `<empty>`,
represents the empty string (12 occurrences).

```text
<empty>
(1st verse)
(2 Times)
(2nd verse)
(2X)
(2x)
(4x)
(Choir)
(Chorus)
(echo)
(Everybody)
(Refrain)
(Repeat 2X)
(Repeat 3X)
(Repeat 4)
(Repeat chorus twice)
(Repeat for A while)
(Repeat)
(repeat)
(Response)
(Solo)
(x4)
*[Bridge]*
*Bridge*
*Chorus*
- Jude 1:2 CEV
1
1.
1st
1st verse
2
2)
2.
2ce
2nd
2nd verse
2x
3
3.
3rd
3rd verse
3x
4
4th
4th verse
4x
5
5th
5x
6x
8X
[2x]
[ALL]
[Bridge x3:]
[Bridge:]
[Bridge]
[BRIDGE]10x
[Chant:]
[choir repeat through out]
[Choir:]
[Chorus 2:]
[Chorus 3:]
[Chorus x2:]
[Chorus: Harmony]
[Chorus:]
[CHORUS]
[Chorus]
[Lead:]
[NARRATIVE]
[Outro]
[Repeat]
[SOLO 1]
[SOLO 2]
[Soloist ad lib throughout]
[Verse 1:]
[verse 1:]
[Verse 1]
[Verse 2:]
[Verse 2]
[Verse 3:]
[Verse 3]
[Verse: Choir (Unison)]
Ad lib
All
All glory, all glory
All honor
All the way
AT THE CENTER
Before the Lord our God
Bridge
Bridge (4x)
Bridge (Repeat)
Bridge:
Call
Call & Response
Ch:
Choir 2
Choir:
CHORUS
Chorus
cHORUS
chorus
Chorus (2x)
Chorus (x2)
CHORUS 1
Chorus 1
CHORUS 2
Chorus 2
CHORUS 3
Chorus 3
Chorus cont
Chorus cont.:
CHORUS:
Chorus:
CHR:
CHROUS
Chrous
cHrous
Chukwu nam gworia ele
Come, come let us adore Him
Confirming your word
Day by day
Don't wanna waste my time giving my attention
Drama
Ewi:
Faith of our fathers, holy faith
For healing the sick
For me and you)
Four Things That Can Kill The Fire of God in Ministers
Hail Your name
Hallowed be your name
He knows my name
He loves me I cannot say why
He loves me I cannot say why.
He suffered for me
Helper (3x)
Here on our knees
Holy are you Lord
Hosanna ! (Chorus)
HOW GREAT THOU ART
I
I have decided to follow Jesus (3x)
In English
In Zulu
INTERLUDE
INTRO
Intro
It is well in the name of Jesus
It is well with my soul today
It is well, It is well,
IYA NI WURA IYEBIYE
Jehovah, You I trust
Jesus we hail
Keywords
Koso babire 2X
Lead
Leadership Session 1
Mighty man of war: Chorus
MOTHER IS A PRECIOUS GEM
Multiple x
My dear friends, I really wanted to write you about God’s saving power at work in our lives. But instead, I must write and ask you to defend the faith that God has once for all given to his people.
Narakele Mo
Never thought I would deserve it
No foreign God
No Longer Slaves
No turning back (2x)
Oh God
On Calvary tree,
Point 1
Point 2
Prayer point 1
Prayer point 2
Prayer point 3
Prayer point 4
Prayer pt.1
Pre-Chorus (2x)
Pre-Song:
Rap:
RCCGNA convention Stream
REFRAIN
Refrain
Refrain b
REFRAIN:
Refrain:
Repea
Repeat
Repeat 1 & 2
Repeat 2x
Repeat 4 & 5
Repeat chorus
repeat x4
Response
responsibility
SCENE 5
Sermon
Sermon 1
Sermon 2
Solo
SOLO 1
SOLO 2
SOLO 2:
Solo 2:
solo 3:
Solo calls
SOLO:
Special Song
Sunday School
Thank you for the latter rain
Thank you for the rain (2x)
The Priests’ Share
There is none like you lord (2x)
V1
Vamp
Vamp:
Verse
verse
VERSE 1
Verse 1
verse 1
Verse 1 Cont
Verse 1 cont
verse 1 cont
Verse 1 cont1
Verse 1 cont2
Verse 1 Continued
Verse 1:
Verse 1b
verse 1b
VERSE 2
Verse 2
verse 2
Verse 2 Cont
Verse 2 cont
Verse 2 Continued
Verse 2:
Verse 2b
Verse 2c
Verse 2d
Verse 3
Verse 3 Cont
Verse 3 cont
Verse 3 Continued
Verse 3:
Verse 3b
Verse 4
verse 4
Verse 4 Cont
Verse 4 Continued
Verse 4:
Verse 4b
Verse 5
verse 5
Verse 5 Continued
Verse 5b
verse 5b
Verse 6
Verse 6b
Verse 7
Verse2
Verse:
Verse: Solo
WE ARE MARCHING TO ZION
We are saying thank you Jesus
We honor You
What Makes A Dad
What shall I render to Jehovah,
With lifted hands
Women Fellowship
x
x2
x3
x4
x8 x8 x7
xxx
Yes You Are
YOU ARE
You are highly lifted up
YOU ARE THE LORD
You deserve it
Your Love is All Around
```

## Import and normalization implications

The source evidence supports preserving exact labels, but the product decision
is to keep that evidence in `raw_lyrics.content` and emit a simpler structured
Song Section:

- `position`: the authoritative order of the label-and-lyrics pair;
- `label`: a normalized category such as `verse`, `chorus`, `bridge`,
  `pre_chorus`, `refrain`, `intro`, `outro`, `solo`, or `vamp`; labels outside
  the recognized vocabulary retain their exact EasyWorship text;
- `slides`: the ordered lyric slides belonging to the section.

EasyWorship numbering such as `Verse 2` or `Chorus 1` is not emitted as a
separate structured field. Repeated normalized labels are distinguished by
their position. The exact source label remains recoverable from the raw RTF.
Unknown, misspelled, empty, and custom labels must not fail the import. They
remain unchanged in the structured section instead of collapsing to `custom`.
Full-text lyric search should index lyric lines, not hidden label text.

## Sample NDJSON song record

This sample makes the raw/derived boundary explicit. In an actual NDJSON file,
the entire object appears on one physical line.

```json
{
  "contract_version": "catalog-import/v1",
  "source": {
    "system": "easyworship",
    "song_rowid": 42,
    "song_uid": "1-EXAMPLE-UID",
    "song_item_uid": "1-EXAMPLE-ITEM-UID"
  },
  "title": "Amazing Grace",
  "author": "John Newton",
  "copyright": null,
  "raw_lyrics": {
    "format": "rtf",
    "content": "{\\rtf1\\ansi ... exact EasyWorship RTF ...}"
  },
  "cleaned_lyrics": "Amazing grace, how sweet the sound\nThat saved a wretch like me\nWe sing of grace\nWe sing of mercy\nGrace has found us\nMercy surrounds us",
  "sections": [
    {
      "position": 1,
      "label": "verse",
      "slides": [
        {
          "position": 1,
          "source_slide_uid": "1-EXAMPLE-SLIDE-UID",
          "lines": [
            "Amazing grace, how sweet the sound",
            "That saved a wretch like me"
          ]
        }
      ]
    },
    {
      "position": 2,
      "label": "chorus",
      "slides": [
        {
          "position": 1,
          "source_slide_uid": "1-EXAMPLE-SLIDE-UID-2",
          "lines": [
            "We sing of grace",
            "We sing of mercy"
          ]
        },
        {
          "position": 2,
          "source_slide_uid": "1-EXAMPLE-SLIDE-UID-3",
          "lines": [
            "Grace has found us",
            "Mercy surrounds us"
          ]
        }
      ]
    }
  ],
  "content_fingerprint": "sha256:..."
}
```

## Remaining uncertainty

The evidence does not identify EasyWorship's complete factory-default label
configuration, because the profile settings that hold configured labels were
not available and the manual's extracted text does not enumerate them. More
importantly, a factory list would not be a complete validation list: the manual
and databases prove that users can create arbitrary labels. A future controlled
Windows export of a fresh default EasyWorship profile could document defaults,
but it should not change the free-form import contract.
