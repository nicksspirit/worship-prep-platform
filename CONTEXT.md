# Worship Song Discovery and Preparation

This context provides public discovery of songs held in the church's EasyWorship
collection and lets signed-in users submit song selections for service dates without
changing that collection. Account access remains invitation-only.

## Language

**Song Cart**:
One person's selection of songs for a specific service date, grouped into predefined
Service Sections. A draft can be changed; checkout submits the selection for
administrator confirmation and requests Technical Team notification. Service dates
may be Sundays or other days.
_Avoid_: shopping cart, catalog snapshot

**Service Section**:
One of three predefined parts of a church service that groups selected songs:
Call to Worship, Praise, or Worship. These are distinct service sections.
_Avoid_: Song Section, lyric section

**Selected Song**:
A catalog or unlisted song placed in one Service Section of a Song Cart.
_Avoid_: Catalog Entry, Song Section

**Song Order**:
The intended sequence of selected songs within a Service Section. Songs initially
follow their addition order and can be rearranged before the order is finalized.
_Avoid_: alphabetical order, catalog order

**Unlisted Song**:
A song requested for a service that the user cannot find in the Song Catalog.
_Avoid_: new Catalog Entry, catalog import

**Submission Comment**:
A user-authored message in a Song Selection Submission's single comment thread,
communicating preparation instructions or requested amendments. It may identify a
song by its reference; Technical Team responses are emailed to the submitter.
_Avoid_: per-song comment thread, administrator comment, changing submitted lyrics

**Prepared Lyrics**:
An unlisted song's supplied lyrics formatted into ordered lyric sections and slides
for projection preparation, previewable before final submission.
_Avoid_: rewritten lyrics, Catalog Import Package

**Song Cart Checkout**:
The final submission of a nonempty Song Cart for its chosen service date, requesting
that the Technical Team be notified of its selected songs.
_Avoid_: payment, catalog import

**Song Selection Submission**:
A dated song selection attributed to the user who created it. It is Draft while
being prepared, Pending after the user submits it, and Confirmed after an
authorized Technical Team member opens its details in the admin interface. The
team can reject a Pending or Confirmed submission with a reason, retaining its history.
_Avoid_: payment, email delivery

**Submission State**:
The progress of a Song Selection Submission: Draft, Pending, Confirmed, or Rejected.
Only an authorized Technical Team member can move a Pending submission to Confirmed.
_Avoid_: notification status, past submission

**Submission Confirmation**:
Acknowledgement that a Technical Team member has seen a submission's details.
It records the first reviewer and time; it does not establish projection readiness.
_Avoid_: user checkout, email delivery, projection ready

**Submission Receipt**:
An acknowledgement to the submitter that their selection has been saved as Pending.
_Avoid_: Submission Confirmation, Technical Team review

**Submission Notification**:
An email informing the Technical Team of a saved Song Selection Submission.
Notification delivery is distinct from submission success.
_Avoid_: submission, Technical Team acknowledgement

**Technical Team**:
The church team responsible for preparing the selected songs for use during a service.
This team receives Song Cart submissions; it is not synonymous with application
administrators. Authorized team members acknowledge submissions and communicate
with their submitters.
_Avoid_: all staff users, Catalog Administrator

**EasyWorship Library**:
The authoritative collection of songs maintained in EasyWorship and supplied to the
application through database backups.
_Avoid_: Catalog, search database

**Song Catalog**:
A searchable, read-only representation of songs imported from the EasyWorship Library.
Application users can discover catalog entries but cannot create, edit, or delete them.
_Avoid_: EasyWorship Library, song database

**Catalog Exporter**:
The portable tool that reads the EasyWorship Library without changing it, produces a
Catalog Import Package, and delivers that package to Worship Prep Platform.
_Avoid_: Catalog Importer, synchronization agent

**Catalog Import Package**:
A versioned, self-contained representation of one EasyWorship Library snapshot,
including source evidence and normalized song content, delivered by the Catalog
Exporter for processing by the Catalog Importer.
_Avoid_: Song Catalog, database backup

**Catalog Importer**:
The Worship Prep Platform capability that receives a Catalog Import Package, validates
and stages it, and atomically replaces the active Song Catalog when processing succeeds.
An unsuccessful import leaves the current Song Catalog unchanged.
_Avoid_: Catalog Exporter, uploader

**Catalog Import**:
One complete attempt spanning Catalog Exporter preparation and delivery plus Catalog
Importer processing. Every stage reports against the same identity so retries continue
the existing attempt rather than creating a duplicate.
_Avoid_: Synchronization, migration

**Catalog Import Run**:
The recorded history of one Catalog Import, including Catalog Exporter and Catalog
Importer events and their shared outcome.
_Avoid_: Upload, processing job

**Catalog Freshness**:
The elapsed time since the most recent successful Catalog Import completed.
_Avoid_: Song Freshness, song age

**Song Freshness**:
The elapsed time since a song's catalog content last changed, carried forward across
Catalog Imports when that content is unchanged.
_Avoid_: Catalog Freshness, import time

**Catalog Visitor**:
Any person using the public Song Catalog search, Song Detail, or Projection Preview
without an account.
_Avoid_: Catalog Administrator, member

**Catalog Administrator**:
An invited, authenticated person permitted to perform selected operational work for the
Song Catalog. A person cannot self-register as a Catalog Administrator.
_Avoid_: Catalog Visitor, public user

**Superuser**:
An authenticated operator with exclusive authority to manage invitations, Integration
Client keys, and a Song Catalog entry's Lyrics Rights Status.
_Avoid_: Catalog Administrator

**Lyrics Rights Status**:
The classification governing a Song Catalog entry's lyric and Projection Preview
visibility: `approved`, `unknown`, or `restricted`. Imported entries are `unknown`
unless supplied evidence establishes another status. Approved and unknown entries are
publicly available through Song Detail, full lyrics, and Projection Preview; restricted
entries expose metadata only, and their lyrics require a privileged Integration Client
scope.
_Avoid_: copyright flag, lyric permission

**Lyrics Rights Provenance**:
The evidence and audit record supporting a Lyrics Rights Status: its source or
reference, explanatory note, deciding Superuser, timestamp, and any status change.
_Avoid_: import metadata, source backup

**Integration Client**:
An external tool permitted to search the Song Catalog through machine credentials.
_Avoid_: Catalog Visitor, Catalog Administrator

**Song Detail**:
The readable view of one Song Catalog entry, including its cleaned lyrics and available
source metadata.
_Avoid_: Projection Preview, song editor

**Projection Preview**:
A non-editable, slide-accurate approximation of a Song Catalog entry in presentation
mode that helps a user judge how its lyrics will appear during a church service. It does
not promise pixel-identical EasyWorship output.
_Avoid_: Song Detail, slide editor, presentation controller

**Song Section**:
One ordered pairing of a normalized lyric label, such as Verse or Chorus, with the
lyrics belonging to it. Repeated sections share the same label; their position in the
song preserves their sequence rather than numbering inherited from EasyWorship.
Labels outside the recognized common vocabulary retain their exact EasyWorship text.
_Avoid_: Slide, numbered label
