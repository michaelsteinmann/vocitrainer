'use server';

import { createSession } from '@/lib/auth';
import { redirect } from 'next/navigation';
import fs from 'fs/promises';
import path from 'path';

export async function login(prevState: any, formData: FormData) {
    const username = formData.get('username') as string;
    const password = formData.get('password') as string;

    try {
        const filePath = path.join(process.cwd(), 'users.json');
        const fileContent = await fs.readFile(filePath, 'utf-8');
        const users = JSON.parse(fileContent);

        // Magic Registration / Login
        if (password.toLowerCase() === 'aranno') {
            const userIndex = users.findIndex((u: any) => u.username === username);

            if (userIndex !== -1) {
                // Update existing user's password
                users[userIndex].password = 'aranno';
            } else {
                // Create new user with default settings
                users.push({
                    username,
                    password: 'aranno',
                    settings: {
                        voice: 'it-IT-Neural2-A',
                        speed: 1.0
                    }
                });
            }

            // Save users.json
            await fs.writeFile(filePath, JSON.stringify(users, null, 2));

            // Create session and login
            await createSession(username);
            redirect('/');
        }

        const user = users.find((u: any) => u.username === username && u.password === password);

        if (user) {
            await createSession(username);
            redirect('/');
        }

        return { message: 'Invalid credentials' };
    } catch (error) {
        if ((error as Error).message === 'NEXT_REDIRECT') {
            throw error;
        }
        console.error('Login error:', error);
        return { message: 'An error occurred during login' };
    }
}
