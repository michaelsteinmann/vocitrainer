import { NextResponse } from 'next/server';
import { getSession } from '@/lib/auth';
import fs from 'fs/promises';
import path from 'path';

const USERS_FILE = path.join(process.cwd(), 'users.json');

export async function GET() {
    const username = await getSession();
    if (!username) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

    try {
        const fileContent = await fs.readFile(USERS_FILE, 'utf-8');
        const users = JSON.parse(fileContent);
        const user = users.find((u: any) => u.username === username);
        if (user) {
            return NextResponse.json(user.settings || {});
        }

        return NextResponse.json({ error: 'User not found' }, { status: 404 });

    } catch (e) {
        console.error(e);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}

export async function POST(request: Request) {
    const username = await getSession();
    if (!username) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    try {
        const { germanVoice, germanSpeed, italianVoice, italianSpeed } = await request.json();
        const fileContent = await fs.readFile(USERS_FILE, 'utf-8');
        const users = JSON.parse(fileContent);

        const userIndex = users.findIndex((u: any) => u.username === username);
        if (userIndex !== -1) {
            // Merge new settings with existing ones
            users[userIndex].settings = {
                ...users[userIndex].settings,
                ...(germanVoice && { germanVoice }),
                ...(germanSpeed && { germanSpeed }),
                ...(italianVoice && { italianVoice }),
                ...(italianSpeed && { italianSpeed })
            };

            await fs.writeFile(USERS_FILE, JSON.stringify(users, null, 2));
            return NextResponse.json(users[userIndex].settings);
        }

        return NextResponse.json({ error: 'User not found' }, { status: 404 });
    } catch (error) {
        console.error('Error updating settings:', error);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}
