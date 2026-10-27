// @ts-check

// Which representation(s) to import for each event:
//   'cnv'     - exon-level deletion of the skipped exon(s); VSClinical names an in-frame
//               exon loss "<Gene> Exon <N> Skipping" (EXON_SKIPPING scope)
//   'variant' - the causal splice-site DNA variant from the SpliceVariant column, if present
//   'both'    - import both (useful for comparing the two in testing)
const MODE = 'both';

/** @type {import('../@types/custom_script').CustomScript} */
export default {
    description: 'Import exon skipping events (e.g. MET exon 14 skipping) from a TSV with columns Gene, SkippedExons and optional Transcript, SpliceVariant',
    binaryFileTypes: [],
    inputFiles: [], // This can be set to import as data or text files in the current dir

    inputType: 'SingleFile', // SingleFile or MultipleFiles or not defined if not input files
    fileFilter: 'Exon Skipping Events (*.tsv *.txt)',
    icon: 'import',

    async run({
        selected, inputs, api: { table, project, cancer, core }, args,
    }) {
        try {
            // args as string[] input list, extended by vspipeline run command context
            const [evalId] = args;
            const evaluationId = parseInt(evalId);

            const [file] = selected;
            const events = parseEvents(file);
            console.log(`Found ${events.length} exon skipping event(s)`);

            async function biomarkerIds() {
                const biomarkers = await cancer.getEvaluationBiomarkers({ evaluationId });
                return new Set(biomarkers.map(b => b.id));
            }

            // addCnv can throw even when the CNV was added, so judge success by whether
            // a new biomarker appeared rather than by the exception
            async function tryAddCnv(cnv) {
                const before = await biomarkerIds();
                try {
                    await cancer.addCnv({ cnv, ratio: null, origin: 'SOMATIC', evaluationId });
                } catch (error) {
                    console.log(`  addCnv threw for "${cnv}": ${error}`);
                }
                const after = await biomarkerIds();
                return [...after].some(id => !before.has(id));
            }

            for (const event of events) {
                const { gene, exons } = event;
                const exonLabel = exons[0] === exons[1] ? `${exons[0]}` : `${exons[0]}-${exons[1]}`;
                console.log(`${gene} exon ${exonLabel} skipping`);

                if (MODE === 'cnv' || MODE === 'both') {
                    const tx = await cancer.preferredTranscriptForGene({ evaluationId, geneName: gene });
                    const txName = event.transcript || (tx && tx.transcriptName);

                    // Query forms used by the shipped Archer and TSO500 splice import scripts. The
                    // transcript form is a last resort: VarSeq 3.1.0 accepts "NM_000245.4 14 DEL"
                    // but ignores the exon and adds a whole-gene deletion
                    const queries = [];
                    const region = tx && exonRegion(tx, exons);
                    if (region) {
                        queries.push(`${region.chr}:${region.start}-${region.stop} DEL`);
                    }
                    if (txName) {
                        queries.push(`${txName} ${exonLabel} DEL`);
                    }

                    let added = false;
                    for (const query of queries) {
                        console.log(`  Adding exon deletion: ${query}`);
                        if (await tryAddCnv(query)) {
                            added = true;
                            break;
                        }
                    }
                    if (!added) {
                        console.log(`  Failed to add ${gene} exon ${exonLabel} as a CNV`);
                    }
                }

                if ((MODE === 'variant' || MODE === 'both') && event.spliceVariant) {
                    console.log(`  Adding splice variant: ${event.spliceVariant}`);
                    try {
                        await cancer.addVariant({ variant: event.spliceVariant, origin: 'SOMATIC', evaluationId });
                    } catch (error) {
                        console.log(`  Failed to add variant ${event.spliceVariant}: ${error}`);
                    }
                }

                await reportExonSkipping(cancer, evaluationId, gene);
            }

            console.log('Done importing exon skipping events');
        } catch (error) {
            console.log(error);
            throw error;
        }
    }
};

/**
 * Tab-delimited with a header row. Required columns: Gene, SkippedExons ("14" or "4-5").
 * Optional: Transcript (defaults to the evaluation's preferred transcript), SpliceVariant (HGVS).
 * Lines starting with '#' are ignored.
 * @param {string} text
 */
export function parseEvents(text) {
    const lines = text.split(/\r?\n/).filter(l => l.trim().length > 0 && !l.startsWith('#'));
    if (lines.length === 0) {
        return [];
    }
    const header = lines[0].split('\t').map(h => h.trim().toLowerCase());
    const col = name => header.indexOf(name.toLowerCase());
    const geneCol = col('Gene');
    const exonCol = col('SkippedExons') >= 0 ? col('SkippedExons') : col('Exon');
    if (geneCol < 0 || exonCol < 0) {
        throw new Error(`Expected Gene and SkippedExons columns, found: ${lines[0]}`);
    }
    const txCol = col('Transcript');
    const spliceCol = col('SpliceVariant');

    return lines.slice(1).map(line => {
        const fields = line.split('\t').map(f => f.trim());
        const exons = fields[exonCol].replace(/^exons?\s*/i, '').split('-').map(e => parseInt(e));
        if (exons.some(isNaN)) {
            throw new Error(`Invalid SkippedExons value: ${fields[exonCol]}`);
        }
        return {
            gene: fields[geneCol],
            exons: [exons[0], exons[exons.length - 1]],
            transcript: txCol >= 0 && fields[txCol] ? fields[txCol] : null,
            spliceVariant: spliceCol >= 0 && fields[spliceCol] ? fields[spliceCol] : null,
        };
    });
}

/**
 * 1-based display coordinates spanning the given exons (exon numbers are in transcript
 * order, so they count from the 3' end of the genome on the minus strand).
 * @param {{chr: string, strand: string, exonCount: number, exonStarts: number[], exonStops: number[]}} tx
 * @param {number[]} exons
 */
export function exonRegion(tx, exons) {
    const idx = n => tx.strand === '-' ? tx.exonCount - n : n - 1;
    const indices = exons.map(idx);
    if (indices.some(i => i < 0 || i >= tx.exonCount)) {
        return null;
    }
    const lo = Math.min(...indices);
    const hi = Math.max(...indices);
    return {
        chr: tx.chr.replace('chr', ''),
        start: tx.exonStarts[lo] + 1,
        stop: tx.exonStops[hi],
    };
}

// Log whether the evaluation now has the gene's exon skipping biomarker, and whether it is
// the selected mutation scope or only one of the possible ones
async function reportExonSkipping(cancer, evaluationId, gene) {
    const biomarkers = await cancer.getEvaluationBiomarkers({ evaluationId });
    let found = false;
    for (const b of biomarkers) {
        if (!b.mutation || !b.mutation.name.startsWith(`${gene} `)) {
            continue;
        }
        const skipping = (b.possibleMutations || []).filter(m => m.annotationScope === 'EXON_SKIPPING');
        if (b.mutation.annotationScope === 'EXON_SKIPPING') {
            console.log(`  OK: biomarker ${b.id} is "${b.mutation.name}" (${b.mutation.description})`);
            found = true;
        } else if (skipping.length > 0) {
            console.log(`  PARTIAL: biomarker ${b.id} is "${b.mutation.name}"; exon skipping is available but not selected: ${skipping.map(m => m.name).join(', ')}`);
            found = true;
        } else {
            console.log(`  Biomarker ${b.id} is "${b.mutation.name}" (${b.mutation.annotationScope}) with no exon skipping scope`);
        }
    }
    if (!found) {
        console.log(`  No ${gene} exon skipping biomarker in the evaluation`);
    }
}
