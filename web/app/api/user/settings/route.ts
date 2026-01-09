import { getSession } from '@/lib/auth';
import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

export async function GET() {
    const username = await getSession();
    if (!username) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    try {
        const filePath = path.join(process.cwd(), 'users.json');
        const fileContent = await fs.readFile(filePath, 'utf-8');
        const users = JSON.parse(fileContent);
        const user = users.find((u: any) => u.username === username);

        if (user) {
            return NextResponse.json(user.settings || {});
        }

        return NextResponse.json({ error: 'User not found' }, { status: 404 });
    } catch (error) {
        console.error('Error fetching settings:', error);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}

export async function POST(request: Request) {
    const username = await getSession();
    if (!username) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    try {
        const { voice, speed } = await request.json();
        const filePath = path.join(process.cwd(), 'users.json');
        const fileContent = await fs.readFile(filePath, 'utf-8');
        const users = JSON.parse(fileContent);

        const userIndex = users.findIndex((u: any) => u.username === username);
        if (userIndex !== -1) {
            users[userIndex].settings = {
                ...users[userIndex].settings,
                voice,
                speed
            };

            await fs.writeFile(filePath, JSON.stringify(users, null, 2));
            return NextResponse.json(users[userIndex].settings);
        }

        return NextResponse.json({ error: 'User not found' }, { status: 404 });
    } catch (error) {
        console.error('Error updating settings:', error);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}
