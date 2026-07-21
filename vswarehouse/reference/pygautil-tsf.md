# pygautil — reading & writing TSF tracks/catalogs (agent field notes)

`pygautil` is the Python library for reading and writing Golden Helix **TSF** annotation files
(tracks and catalogs). It lives at `/opt/apiserver/` — set `PYTHONPATH=/opt/apiserver` in any
`docker` step that imports it (see [`environment.md`](./environment.md)).

Authoritative API reference on this server: `/opt/frontend/docs/tools/pygautil.md`. This file is
the operational cheat-sheet + the gotchas that reference doesn't spell out.

```python
import pygautil
```

## Server auto-detection — don't set the coordinate system by hand
Inside a task container `pygautil` reads the server env vars and configures itself. The
workspace assembly (see `GH_WORKSPACE_ASSEMBLY`, GRCh38 by default) is already loaded. **Do
not** call `setCoordSysId` / `setReferenceSequenceSource` / `setTranscriptSource` at startup —
the only time you switch is to emit a GRCh37 output mid-script (see "Multi-build" below).

## Schema type codes
| Code | Type | | Code | Type |
|---|---|---|---|---|
| `s` | String | | `?` | Boolean |
| `i` | Integer | | `e` | Enum (finite string domain) |
| `f` | Float | | `@s` `@i` `@f` | Array of string / int / float |

Schema string is tab-separated `Field Name=typecode` pairs:
`"Gene Name=s\tScore=f\tClassification=e\tPubMed IDs=@s"`.

## Writing a genomic track
```python
writer = pygautil.createTrack(
    "output.tsf",                       # output URL/path
    "MyTrack 2026-07-20",               # title
    "interval",                         # "variant" | "interval" | "sequence"
    "GRCh_38,Chromosome,Homo sapiens",  # full coord-sys string
    "Gene Name=s\tScore=f\tClass=e",    # schema
    descriptionHtml="<p>...</p>",
    sourceCreditHtml="<p>Source: ...</p>",
    seriesName="MyTrack",
    sourceVersion="2026-07-20",
    fieldDocs={"Gene Name": "HGNC symbol", "Score": "0..1", "Class": "Benign|Pathogenic"},
)
writer.writeFeature("17", 7_670_000, 7_690_000, ["TP53", 0.95, "Pathogenic"])  # (chr, start, stop, [values])
writer.flush()
out_url = writer.finish()               # ALWAYS flush() then finish(); finish() returns the URL

# Sort / left-align / index as a post-process
sorted_url = pygautil.convert([out_url], {   # note: [list_of_files] + options dict
    "coverage": "IntervalCoverage",          # "VariantCoverage" for variant tracks
    "leftAlign": True,                       # variant tracks only
    "indexFields": ["Gene Name"],
    "outputFileName": "output_sorted.tsf",
})
pygautil.lockTrack(sorted_url)               # seal as immutable
```

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
    gene, score = reader.next()          # tuple in the field order you requested
info = pygautil.getInfo("track.tsf")     # info["locusCount"], info["fields"], info["name"], ...
```
Other read entry points: `readByOffset(0)` + `hasNext()`/`next()` for a full scan,
`coverageSpace()` + `readChr(...)` to walk chromosome by chromosome, `readByPrefixSearch(prefix,
field, fields)` for indexed prefix lookups.

## Coordinate / HGVS helpers
```python
pygautil.convertCdot("NM_000546.4:c.-123C>G")        # -> [['17', 7687470, 7687471, 'G/C', '']]
pygautil.getGeneCoordinates("TP53")                  # chr, start, stop, ...
pygautil.getExonCoordinates("TP53", 5)
pygautil.liftover("17", 7687470, 7687471, "G/C", "GRCh_37_g1k")   # chain files may be absent
```

## Multi-build (GRCh38 + GRCh37 in one script)
Finalize GRCh38 first (default coord sys), then switch before finalizing GRCh37:
```python
writer38.flush(); url38 = writer38.finish(); pygautil.convert([url38], {...})
pygautil.setCoordSysId("GRCh_37_g1k,Chromosome,Homo sapiens")
pygautil.setReferenceSequenceSource(
    "/workspace/AppData/Common Data/Annotations/ReferenceSequence-NCBI_GRCh_37_g1k_Homo_sapiens.tsf")
writer37.flush(); url37 = writer37.finish(); pygautil.convert([url37], {...})
```
Skipping the switch when `leftAlign: True` raises
`ValueError: The required Reference Sequence was not found as a local source.` Gene/region
tracks that don't left-align don't need the switch.

## Gotchas that cost time
- `createTrack` takes **positional args + kwargs**, not a dict.
- `writeFeature(chr, start, stop, [values])` — the values are a **list**, in schema order.
- **Always `flush()` then `finish()`** before exit; `finish()` returns the output URL.
- `convert()` takes `[list_of_files]` + an options dict — not two path args.
- Intermediate TSFs go to `/scratch`; only final sorted outputs go to a persistent location.
