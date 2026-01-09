
import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const DATA_DIR = path.join(process.cwd(), 'public/data/vocabulary');

export async function GET() {
    try {
        if (!fs.existsSync(DATA_DIR)) {
            return NextResponse.json([]);
        }

        const files = fs.readdirSync(DATA_DIR)
            .filter(file => file.endsWith('.json') && file !== 'index.json');

        const index = files.map(file => {
            const filePath = path.join(DATA_DIR, file);
            const stats = fs.statSync(filePath);
            const content = JSON.parse(fs.readFileSync(filePath, 'utf-8'));

            return {
                name: file.replace('.json', ''),
                fileName: file,
                count: Array.isArray(content) ? content.length : 0,
                lastModified: stats.mtime
            };
        });

        return NextResponse.json(index);
    } catch (error) {
        console.error('API Error:', error);
        return NextResponse.json({ error: 'Failed to list files' }, { status: 500 });
    }
}
