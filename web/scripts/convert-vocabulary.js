const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const SOURCE_DIR = path.join(__dirname, '../../Excel-Files_als_Quellen');
const OUTPUT_DIR = path.join(__dirname, '../public/data/vocabulary');
const INDEX_FILE = path.join(OUTPUT_DIR, 'index.json');

// Ensure output directory exists
if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

const files = fs.readdirSync(SOURCE_DIR).filter(file => file.endsWith('.xlsx') && !file.startsWith('~$'));

const index = [];

files.forEach(file => {
    console.log(`Processing ${file}...`);
    try {
        const filePath = path.join(SOURCE_DIR, file);
        const workbook = XLSX.readFile(filePath);
        const sheetName = workbook.SheetNames[0];
        const sheet = workbook.Sheets[sheetName];
        const data = XLSX.utils.sheet_to_json(sheet);

        const jsonFileName = file.replace('.xlsx', '.json');
        const outputFilePath = path.join(OUTPUT_DIR, jsonFileName);

        fs.writeFileSync(outputFilePath, JSON.stringify(data, null, 2));

        // Get file stats for display
        const stats = fs.statSync(filePath);

        index.push({
            name: file.replace('.xlsx', ''),
            fileName: jsonFileName,
            originalFile: file,
            count: data.length,
            lastModified: stats.mtime
        });

        console.log(`  -> Saved to ${jsonFileName} (${data.length} entries)`);

    } catch (error) {
        console.error(`  Error processing ${file}:`, error.message);
    }
});

fs.writeFileSync(INDEX_FILE, JSON.stringify(index, null, 2));
console.log(`\nIndex file created at ${INDEX_FILE} with ${index.length} entries.`);
