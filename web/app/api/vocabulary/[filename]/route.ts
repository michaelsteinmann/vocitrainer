
import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const DATA_DIR = path.join(process.cwd(), 'public/data/vocabulary');

function getFilePath(filename: string) {
    // Basic sanitization
    const safeName = path.basename(filename);
    return path.join(DATA_DIR, safeName);
}

interface RouteParams {
    params: Promise<{ filename: string }>;
}

export async function GET(request: Request, { params }: RouteParams) {
    try {
        const { filename } = await params;
        const filePath = getFilePath(filename);

        if (!fs.existsSync(filePath)) {
            return NextResponse.json({ error: 'File not found' }, { status: 404 });
        }

        const content = fs.readFileSync(filePath, 'utf-8');
        const json = JSON.parse(content);

        return NextResponse.json(json);
    } catch (error) {
        console.error('API Error:', error);
        return NextResponse.json({ error: 'Failed to read file' }, { status: 500 });
    }
}

export async function PUT(request: Request, { params }: RouteParams) {
    try {
        const { filename } = await params;
        const filePath = getFilePath(filename);
        const data = await request.json();

        if (!Array.isArray(data)) {
            return NextResponse.json({ error: 'Invalid data format. Expected array.' }, { status: 400 });
        }

        fs.writeFileSync(filePath, JSON.stringify(data, null, 2));

        return NextResponse.json({ success: true, count: data.length });
    } catch (error) {
        console.error('API Error:', error);
        return NextResponse.json({ error: 'Failed to save file' }, { status: 500 });
    }
}

export async function DELETE(request: Request, { params }: RouteParams) {
    try {
        const { filename } = await params;
        const filePath = getFilePath(filename);

        if (fs.existsSync(filePath)) {
            fs.unlinkSync(filePath);
        }

        return NextResponse.json({ success: true });
    } catch (error) {
        console.error('API Error:', error);
        return NextResponse.json({ error: 'Failed to delete file' }, { status: 500 });
    }
}
