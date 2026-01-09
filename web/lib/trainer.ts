import * as XLSX from 'xlsx';

// --- Types ---

export interface Card {
    row_index: number;
    prompt: string;
    answers: string[];
    explanation?: string;
    example?: string; // Foreign language example
    german_example?: string;
    prompt_is_german: boolean;
    german_synonyms?: string[];
    pos_code?: string; // 'ADJ', 'ADV', 'NOM', etc.
}

export type AnswerStatus = 'correct' | 'synonym' | 'wrong';

export interface AnswerResult {
    status: AnswerStatus;
    feedback: string;
    isCorrect: boolean; // true if status is 'correct' or 'synonym'
}

// --- Normalization ---

/**
 * Robust normalizer for comparisons:
 * - Lowercase
 * - Removes control characters, tabs, newlines
 * - Keeps only letters (including accents)
 * - Removes extra whitespace
 */
export function normalizeAnswer(s: string | null | undefined): string {
    if (!s) return "";

    // Lowercase and basic cleanup
    let str = String(s).replace(/\r/g, "").replace(/\n/g, "").trim().toLowerCase();

    // Normalize unicode (NFD) to separate accents, then strictly we might want to keep accents 
    // but the python regex `[^a-zàèéìíòóùúäöüß]` suggests we keep specific accented chars.
    // In JS, we can just remove anything that is NOT a letter.
    // However, the python version `unicodedata.normalize("NFKD", s)` separates chars.
    // Then it replaces ellipsis `\u2026` with `...`.
    // Then replaces non-breaking spaces with space.
    // Then removes anything not in the allowlist.

    str = str.normalize("NFKD");
    str = str.replace(/\u2026/g, "..."); // … -> ...

    // Replace various spaces with standard space
    const spaces = ["\u00A0", "\u2009", "\u200A", "\u2002", "\u2003", "\u202F", "\t"];
    spaces.forEach(sp => {
        str = str.split(sp).join(" ");
    });

    // Python allow list: a-z àèéìíòóùú äöü ß
    // In JS regex:
    // We'll strip diacritics ONLY if they are not in the "keep" list, but NFKD separates them.
    // So 'é' becomes 'e' + '́'. If we filter by `[^a-z...]`, the combining mark might be lost if not included.
    // BUT the Python regex includes `à` etc literal code points.
    // Simplest approach matching the Python intent:
    // 1. Remove non-alphanumeric (but keep specific accents if possible, or just strict match python).
    // The Python regex `[^a-zàèéìíòóùúäöüß]` implies it keeps these *specific* chars.
    // Since we did NFKD, 'à' might be 'a\u0300'.
    // Let's stick to a simpler approach that works for 99% of cases:

    // Re-compose to NFC to get characters back together for regex matching
    str = str.normalize("NFC");

    // Remove all characters except a-z and specific accents and german chars
    // Regex based on python: [^a-zàèéìíòóùúäöüß]
    str = str.replace(/[^a-zàèéìíòóùúäöüß]/g, "");

    return str;
}

// --- Excel Parsing & Deck Building ---

export async function parseExcelFile(file: File): Promise<any[]> {
    const arrayBuffer = await file.arrayBuffer();
    const workbook = XLSX.read(arrayBuffer);

    // For now, simpler: getting the first sheet or merging?
    // The python app allowed merging. Let's start with just getting all data from all sheets or first sheet.
    // Let's mimic "All Sheets" behavior by default or ask. 
    // For MVP: Flatten all sheets.

    let allRows: any[] = [];

    workbook.SheetNames.forEach(sheetName => {
        const sheet = workbook.Sheets[sheetName];
        const rows = XLSX.utils.sheet_to_json(sheet);
        allRows = allRows.concat(rows);
    });

    return allRows;
}

export function buildDeck(
    data: any[],
    promptCol: string,
    answerCols: string[], // multiple columns allowed for answers
    filters: {
        niveaus?: string[]; // A1, A2...
        frequency?: string[]; // 1, 2...
    },
    reverse: boolean = false
): Card[] {
    const cards: Card[] = [];

    // Helper to find columns case-insensitively
    const findCol = (row: any, name: string) => {
        const key = Object.keys(row).find(k => k.toLowerCase().trim() === name.toLowerCase().trim());
        return key ? row[key] : undefined;
    };

    const getColValue = (row: any, colName: string): string => {
        // Direct match
        if (row[colName] !== undefined) return String(row[colName]);
        // Case-insensitive match 
        const val = findCol(row, colName);
        return val !== undefined ? String(val) : "";
    };

    // Identify utility columns
    const headerRow = data[0] || {};
    const allKeys = Object.keys(headerRow);

    // Heuristics for special columns (similar to Python)
    const deSynCols = allKeys.filter(k => k.trim().toLowerCase().startsWith("deutsch"));
    const explCol = allKeys.find(k => ["erläuterung", "erklärung", "explanation"].some(c => k.toLowerCase().includes(c)));
    const exIterCol = allKeys.find(k => k.toLowerCase().includes("beispielsatz in der fremdsprache"));
    const exDeCol = allKeys.find(k => k.toLowerCase().includes("beispielsatz deutsch"));
    const posCol = allKeys.find(k => k.toLowerCase().includes("wortart"));
    const niveauCol = allKeys.find(k => k.toLowerCase().includes("niveau"));
    const freqCol = allKeys.find(k => k.toLowerCase().includes("häufigkeit") || k.toLowerCase().includes("haufigkeit"));

    data.forEach((row, idx) => {
        // 1. Filter Check
        if (filters.niveaus && filters.niveaus.length > 0) {
            if (niveauCol) {
                const val = getColValue(row, niveauCol).trim();
                if (val && !filters.niveaus.includes(val)) return;
            }
        }
        if (filters.frequency && filters.frequency.length > 0) {
            if (freqCol) {
                const val = getColValue(row, freqCol).trim();
                // "1.0" -> "1" cleanup
                const fVal = val.split('.')[0];
                if (val && !filters.frequency.includes(fVal)) return;
            }
        }

        // 2. Build Card
        if (!reverse) {
            // Normal: Prompt -> Answers
            const prompt = getColValue(row, promptCol).trim();
            if (!prompt) return;

            const answers: string[] = [];
            answerCols.forEach(col => {
                const val = getColValue(row, col).trim();
                if (val) {
                    // Split on ; if contains multiple
                    val.split(/[;|]/).forEach(v => {
                        if (v.trim()) answers.push(v.trim());
                    });
                }
            });

            if (answers.length === 0) return;

            // German synonyms
            let german_synonyms: string[] = [];
            deSynCols.forEach(c => {
                const v = getColValue(row, c).trim();
                if (v) german_synonyms.push(v);
            });
            // If prompt is in german cols, remove it from synonyms
            const isGermanPrompt = deSynCols.some(dc => dc.toLowerCase() === promptCol.toLowerCase());
            if (isGermanPrompt) {
                german_synonyms = german_synonyms.filter(s => s !== prompt);
            }

            cards.push({
                row_index: idx,
                prompt,
                answers,
                explanation: explCol ? getColValue(row, explCol).trim() : undefined,
                example: exIterCol ? getColValue(row, exIterCol).trim() : undefined,
                german_example: exDeCol ? getColValue(row, exDeCol).trim() : undefined,
                pos_code: posCol ? getColValue(row, posCol).trim() : undefined,
                prompt_is_german: isGermanPrompt,
                german_synonyms: german_synonyms.length > 0 ? german_synonyms : undefined
            });

        } else {
            // Reverse: Answer Col Val -> Prompt Col Val (Single)
            // Need to create one card per selected answer column
            answerCols.forEach(ansCol => {
                const val = getColValue(row, ansCol).trim();
                if (!val) return;

                // The prompt is the original promptCol value
                const originalPrompt = getColValue(row, promptCol).trim();
                if (!originalPrompt) return;

                // Split prompt (because original prompt might have multiple separated by ;)
                // Actually the python logic: 
                // "answers = value from the prompt column (single expected)"
                // But in `Vocitrainer`: `answers=[answer_value]` where checkAnswer allows synonyms.

                // For reverse: 
                // New Prompt: value from `ansCol` (e.g. Italian word)
                // New Answer: value from `promptCol` (e.g. German word)

                // Check if this card's "Prompt" (which is the Italian word) is effectively German? 
                // Usually `ansCol` is Italian, so `prompt_is_german` = false.
                const isGermanNewPrompt = deSynCols.some(dc => dc.toLowerCase() === ansCol.toLowerCase());

                cards.push({
                    row_index: idx,
                    prompt: val, // Italian
                    answers: [originalPrompt], // German
                    explanation: explCol ? getColValue(row, explCol).trim() : undefined,
                    example: exIterCol ? getColValue(row, exIterCol).trim() : undefined,
                    german_example: exDeCol ? getColValue(row, exDeCol).trim() : undefined,
                    pos_code: posCol ? getColValue(row, posCol).trim() : undefined,
                    prompt_is_german: isGermanNewPrompt
                    // German synonyms would be irrelevant if prompt is Italian, 
                    // unless we want to show them as answers? 
                    // Python logic handles "Synonyms" display differently.
                });
            });
        }
    });

    return cards;
}

// --- Status Classification ---

export function checkAnswer(input: string, card: Card, deckCards: Card[]): AnswerResult {
    const normInput = normalizeAnswer(input);

    // 1. Direct Match
    const directMatches = card.answers.map(a => normalizeAnswer(a));
    if (directMatches.includes(normInput)) {
        return { status: 'correct', isCorrect: true, feedback: 'Richtig!' };
    }

    // 2. Intra-Card Synonym Match
    // If prompt is German, then german_synonyms are NOT answers, they are synonyms of the PROMPT.
    // If prompt IS NOT German (Italian), then german_synonyms might be valid answers?
    // Python Logic:
    // Case 1: Prompt is German. Accept index (global Italian variants for this German lemma).
    // Case 2: Prompt is NOT German. If we have explicit German synonyms for the row, treat them as acceptable.

    // We need the "Global Accept Index" equivalent. 
    // In strict mode without the global index for now, we check minimal synonyms.

    // Check global synonyms if available (simple version: scan all cards with same prompt?)
    // This is expensive O(N) per check if not indexed.
    // Let's rely on basic logic first.

    if (!card.prompt_is_german && card.german_synonyms) {
        const synMatches = card.german_synonyms.map(s => normalizeAnswer(s));
        if (synMatches.includes(normInput)) {
            return { status: 'synonym', isCorrect: true, feedback: 'Korrektes Synonym' };
        }
    }

    // 3. Global meaning cloud (if same German prompt appears in other rows with different Italian answers)
    // We can search the deck for other cards with the SAME prompt (if prompt is German)
    if (card.prompt_is_german) {
        const otherCards = deckCards.filter(c => c.prompt === card.prompt && c.row_index !== card.row_index);
        for (const oc of otherCards) {
            const ocAnswers = oc.answers.map(a => normalizeAnswer(a));
            if (ocAnswers.includes(normInput)) {
                return { status: 'synonym', isCorrect: true, feedback: 'Richtig (andere Variante)' };
            }
        }
    }

    return {
        status: 'wrong',
        isCorrect: false,
        feedback: `Falsch. Richtig wäre: ${card.answers.join(', ')}`
    };
}
