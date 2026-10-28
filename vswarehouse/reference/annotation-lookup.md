# Querying annotation sources through the server (Lookup API)

Use the per-workspace Lookup API (`/w/$GH_WORKSPACE_ID/api/lookup/...`, live spec at
`/w/$GH_WORKSPACE_ID/api/lookup.yaml`) to query any annotation source the server knows (built-in
annotations, User Annotations, network sources) without opening files. For bulk scans of a local
TSF, `pygautil` ([`pygautil-tsf.md`](./pygautil-tsf.md)) is still the right tool.

Auth: send `Cookie: GH_SessKey=$GH_SESSION_KEY` (see [`environment.md`](./environment.md)).
Never echo the key. The examples below use this shell helper:

```bash
lk() {  # lk <path under api/> <json body>
  curl -s -X POST -H "Cookie: GH_SessKey=$GH_SESSION_KEY" -H 'Content-Type: application/json' \
       -d "$2" "$GH_SERVER_URL/w/$GH_WORKSPACE_ID/api/$1"
}
```

## 1. Make a new source visible
A file just copied into `AppData/Common Data/UserAnnotations/` (or any annotation location) is
not in the source index until the annotation folders are rescanned. Until then lookups that name
it fail: older builds say `Source not found in local watchers`, or give an empty error for a
`series`; newer builds name the series or file and point at the refresh. Rescan once:

```bash
lk annotations/refresh '{}'      # -> "REFRESH_COMPLETE", returned after the rescan finishes
```

POST only; a GET on that URL is a 404. It is not in any of the OpenAPI specs (it belongs to the
annotations resolver, not the Lookup API). The UI equivalent is the refresh icon next to
"Locations" in the Annotations view. Safe to repeat.

## 2. Resolve the source and read its schema
```bash
lk lookup/resolve '{"source":{"series":"FDA-Drug-Labels"},"includeFields":true}'
```

Without `includeFields:true` there is no `fields` array. Each field has `name` (`Set ID`),
`symbol` (`SetID`), `isIndexed`, `dataType` (`@s` = multi-value string) and `doc`. Read `doc`:
curated tracks explain their normalization rules there.

Addressing a source:
- `{"series": "<seriesName>"}`: latest version on the workspace build. Add
  `"version": "<sourceVersion>"` to pin one.
- `{"sourceUrl": "<file name>.tsf:1"}`: an exact file, by **bare file name**. This is the last
  path segment of the `url` that `resolve`/`listSources` return, not the whole `url`. It is not
  filtered by build.
- `{"catalogId": "<id>"}` for a workspace catalog.

## 3. Look up records by key
```bash
lk lookup/table/lookup '{"source":{"series":"FDA-Drug-Labels"},
  "lookupField":"Drug", "lookupValue":"dostarlimab", "lookupMode":"ExactCaseInsensitive",
  "fieldNames":["Brand Name","Set ID","Indications and Usage"], "limit":20}'
```

- `lookupField` must be **indexed** (`isIndexed: true`). Name or symbol both work.
- Pick the returned fields with **one** selector. If several are sent, `fieldIndexes` wins, then
  `fieldSymbols` (`fieldExpressions` on `table/read` and `genomic/query`), then `fieldNames`.
  `fieldNames` takes display names only; `fieldSymbols` takes symbols (and expressions).
- **Response `objects[]` are keyed by SYMBOL, whichever selector you used:**
  `obj["SetID"]`, `obj["BrandName"]`, `obj["IndicationsandUsage"]`. Not `obj["Set ID"]`.
- To get the name ↔ symbol map in the same response, send `"format":["objects","fieldMetas"]`;
  `fields[]` is only present when `fieldMetas` is requested.

Errors worth recognizing:

| Error | Meaning |
|---|---|
| 400 `Lookup field 'X' is not indexed` | Choose a field with `isIndexed: true`. |
| 400 `Lookup field 'X' not found` | Neither a name nor a symbol of this source. |
| 400 `Field name not found: SetID` | You put a symbol in `fieldNames`; use `fieldSymbols` or the name. |
| `Source not found…` / `No source found in series…` / empty error | Step 1 (refresh), or the series is on another build (use `sourceUrl`). |

`table/read` (paged full read with optional `filterTree`) and `genomic/query/<region>` (region
overlap) take the same source and field selectors and return the same symbol-keyed `objects`.
Page with `enableCursor:true` and `lookup/continue/<cursor>`.

## 4. Python
`ghclient` has no Lookup sub-client; call the endpoints directly.

```python
import json, os, urllib.request

def gh_api(path, body):
    url = f"{os.environ['GH_SERVER_URL']}/w/{os.environ['GH_WORKSPACE_ID']}/api/{path}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
        'Cookie': 'GH_SessKey=' + os.environ['GH_SESSION_KEY'],
        'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=60))

gh_api('annotations/refresh', {})          # only after adding a file
hits = gh_api('lookup/table/lookup', {
    "source": {"series": "FDA-Drug-Labels"}, "lookupField": "Drug",
    "lookupValue": "dostarlimab", "lookupMode": "ExactCaseInsensitive",
    "fieldNames": ["Set ID", "Indications and Usage"]})['objects']
print(hits[0]['SetID'])                     # symbol keys
```

## 5. GET endpoints: encode spaces as `%20`
`lookup/default-transcript-for-gene`, `lookup/gene-transcripts` and other GET endpoints take
`assembly=GRCh_38,Chromosome,Homo sapiens` (`$GH_WORKSPACE_ASSEMBLY`). The server does not decode
`+` as a space, so it rejects `Homo+sapiens` with "Assembly … does not match workspace build",
which reads like a data problem. Python's `urllib.parse.urlencode` and `requests`' `params=` both
emit `+`. Use `urlencode(params, quote_via=urllib.parse.quote)`, or `curl -G --data-urlencode`.

## 6. Gene → default transcript (what the frontend scope editor does)
```text
GET lookup/gene?query=BRCA2&includePrefixMatches=false&includeAliases=false&limit=1   -> geneId
GET lookup/default-transcript-for-gene?assembly=GRCh_38%2CChromosome%2CHomo%20sapiens&geneId=<id>
    -> transcriptName, chr, start, stop
```
The default transcript is the workspace GenePreferences `PreferredTranscript` when set, else the
canonical pick (MANE Select, then LRG, completeness, length). The transcript span differs from the
gene span (BRCA2: gene starts 32315076, NM_000059.4 starts 32315507). Gene-level biomarker scopes
use the **transcript** span.
