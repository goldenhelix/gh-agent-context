# pygautil — reading & writing TSF tracks/catalogs (agent field notes)

`pygautil` is the Python library for reading and writing Golden Helix **TSF** annotation files
(tracks and catalogs). It ships in the server image at `/opt/apiserver/`, which the image already
puts on `PYTHONPATH`, so `import pygautil` works as-is in a `cmd` step or any step running the
default image. A `docker` step on some other image gets nothing (nothing is mounted) — base that
image on the server image instead of trying to set PYTHONPATH yourself.

Signatures and every option: `/opt/apiserver/pygautil.pyi` (matches this container's binary;
`python3 -c "help('pygautil')"` also works). Prose reference: `/opt/frontend/docs/tools/pygautil.md`.
This file is the gotchas those two don't spell out (or get wrong).

```python
import pygautil
```

## Server auto-detection — don't set the coordinate system by hand
Inside a task container `pygautil` reads the server env vars and configures itself. GRCh38 is
the *workspace* default (the server exports it as `GH_WORKSPACE_ASSEMBLY`). With that variable
unset, `pygautil` falls back to GRCh_37_g1k — check `pygautil.getCoordSysId()` if you're running
outside a task/app container. **Do not** call `setCoordSysId` / `setReferenceSequenceSource` /
`setTranscriptSource` at startup — the only time you switch is to emit a GRCh37 output mid-script
(see "Multi-build" below).

## Schema type codes
Field type codes and the schema string format (tab-separated `Field Name=typecode` pairs) are in
`pygautil.pyi` next to `createTrack`/`createTabular`/`createCatalog`. Common ones you'll type from
memory: `s` string, `i` integer, `f` float, `e` enum, `@s`/`@i`/`@f` array of string/int/float.

## Writing a genomic track
Full kwarg list for `createTrack`/`createTabular`/`createCatalog`: `pygautil.pyi`. Shape:
```python
writer = pygautil.createTrack(
    "output.tsf",                       # output URL/path
    "MyTrack 2026-07-20",               # title
    "interval",                         # "variant" | "interval" | "sequence"
    "GRCh_38,Chromosome,Homo sapiens",  # full coord-sys string
    "Gene Name=s\tScore=f\tClass=e",    # schema
    seriesName="MyTrack",
    sourceVersion="2026-07-20",
    fieldDocs={"Gene Name": "HGNC symbol", "Score": "0..1", "Class": "Benign|Pathogenic"},
)
writer.writeFeature("17", 7_670_000, 7_690_000, ["TP53", 0.95, "Pathogenic"])  # chr, start, stop, [values]
writer.flush()
out_url = writer.finish()               # ALWAYS flush() then finish(); finish() returns the URL

# Sort / left-align / index as a post-process
sorted_url = pygautil.convert([out_url], {   # note: [list_of_files] + options dict
    "leftAlign": True,                       # variant tracks only
    "indexFields": ["Gene Name"],
    "outputFileName": "output_sorted.tsf",
})
pygautil.lockTrack(sorted_url)               # seal as immutable
```
`coverage` is only for feature types that have a coverage precompute: `VariantCoverage` (variant
tracks), `VariantMapCoverage`, `SequenceCoverage`. Interval/generic tracks have none — passing
`IntervalCoverage` fails the convert with `No precompute is available for usage
'IntervalCoverage'`.

## Tabular tracks & catalogs (non-genomic)
```python
w = pygautil.createTabular("MONDO.tsf", "MONDO 2026-07-20",
                           "Name=s\tMONDO ID=s\tGenes=@s", seriesName="MONDO", fieldDocs={...})
w.writeRecord(["Disease X", "MONDO:0000001", ["GENE1", "GENE2"]])   # no coords
w.flush(); w.finish()

cat = pygautil.createCatalog("pubmed.catalog", "PubMed", "tabular", "GRCh_38",
                             "PubMed ID=s\tTitle=s\tYear=i",
                             ["PubMed ID"],      # primaryKeys
                             ["PubMed ID"])      # indexFields
cat.writeRecord(["12345678", "Title", 2026]); cat.flush(); cat.finish()
```

## Reading
```python
reader = pygautil.openForRead("track.tsf")
reader.readRegion("17", 7_670_000, 7_690_000, ["Gene Name", "Score"])
while reader.hasNext():
    gene, score = reader.next()          # list, in the field order you requested; [] when exhausted
info = pygautil.getInfo("track.tsf")     # info["locusCount"], info["fields"], info["name"], ...
```
Other read entry points: `readByOffset(0)` + `hasNext()`/`next()` for a full scan,
`coverageSpace()` + `readChr(...)` to walk chromosome by chromosome (`coverageSpace()` rows are
`[chr, start, stop]` with start/stop as **strings** — use `seg[0]` with `readChr`, or `int(seg[1])`,
`int(seg[2])` for `readRegion`), `readByPrefixSearch(prefix, field, fields)` for indexed prefix
lookups. `readRegion(chr, start, -1, fields)` reads the whole chromosome; `chr=""` reads the whole
source.

Beyond I/O, the module also exposes `runTaskList` / `transformOptions` (run gautil transforms
in-process from a YAML-or-dict task list), `latestInSeries` (resolve a source from the loaded
annotation index), `variantTranscripts` / `variantTranscriptsForCdot` / `nearbyClassifiedVariants`,
and metadata patching (`getMeta` / `updateSourceMeta`) — see the `.pyi`, and note the module has a
few entry points the `.pyi` doesn't document (`latestInSeries`, `getUserAnnotationsPath`,
`getGenePreferencesUrl`, `getGeneListsUrl`, `setDataPath`), so `dir(pygautil)` is the last word.

## Coordinate / HGVS helpers
These helpers do not raise on a bad input: on failure they return a single-element list holding
the error message. Check `len(result) > 1` (or `< 4`/`< 3` as appropriate) before unpacking.
```python
chrom, start, stop, refalt, warn = pygautil.convertCdot("NM_000546.4:c.-123C>G")
# -> ['17', 7687470, 7687471, 'G/C', '']   (convertPdot, not convertCdot, returns a list of such rows)
pygautil.getGeneCoordinates("TP53")                  # -> ['17', 7668401, 7687549]
pygautil.getExonCoordinates("TP53", 4)   # exon index is 0-based -> exon 5; -1 = last exon; accepts NM_/ENST too
pygautil.liftover("17", 7687470, 7687471, "G/C", "GRCh_37_g1k")
# liftover only knows human GRCh37<->GRCh38 chains, under %SysData%/liftover/*.chain.gz;
# failures include "Sequence intersects no chains" and a missing-chain-file message.
```
`convertPdot` returns the changed base(s), not the codon: KRAS G12C comes back as a one-base SNV.
A codon-level scope must expand to the full reference codon (`stop - start == 3`).

## Multi-build (GRCh38 + GRCh37 in one script)
Finalize GRCh38 first (default coord sys), then switch before finalizing GRCh37:
```python
writer38.flush(); url38 = writer38.finish(); pygautil.convert([url38], {...})
pygautil.setCoordSysId("GRCh_37_g1k,Chromosome,Homo sapiens")
writer37.flush(); url37 = writer37.finish(); pygautil.convert([url37], {...})
```
`setCoordSysId` alone is enough: it re-resolves the transcript source, reference sequence and
left aligner for the new build. When the tracks you convert already carry their own coordSysId,
`convert()` picks the matching reference per input, so no switch is needed at all (`leftAlignCoord`
overrides it explicitly). If a source lacks any registered reference for a build, `convert(...,
{"leftAlign": True})` raises `ValueError: The required Reference Sequence was not found for build
GRCh_37_g1k,Chromosome,Homo sapiens.` (or a "... is only available remotely and must be downloaded
as a local source" variant when only a network copy is registered). To resolve a reference
explicitly rather than hardcoding a path, use `pygautil.latestInSeries("ReferenceSequence",
"GRCh_37_g1k,Chromosome,Homo sapiens")` (falls back to series `ReferenceSequence-NCBI`) — filenames
under `%Annotations%`/`$WORKSPACE_DIR` embed the curator and often a date, so don't guess them.

## Gotchas that cost time
- `createTrack` takes **positional args + kwargs**, not a dict.
- `writeFeature(chr, start, stop, [values])` — the values are a **list**, in schema order.
  Coordinates are 0-based half-open everywhere (`start = POS - 1`, `stop = POS`); a zero-width
  span is an insertion.
- **Always `flush()` then `finish()`** before exit; `finish()` returns the output URL.
- `convert()` takes `[list_of_files]` + an options dict — not two path args.
- Intermediate TSFs go to `/scratch`; only final sorted outputs go to a persistent location.
