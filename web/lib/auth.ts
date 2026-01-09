import { cookies } from 'next/headers';

const COOKIE_NAME = 'auth_session';

export async function createSession(username: string) {
    const cookieStore = await cookies();
    cookieStore.set(COOKIE_NAME, username, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        path: '/',
        maxAge: 60 * 60 * 24 * 7, // 1 week
    });
}

export async function getSession() {
    const cookieStore = await cookies();
    const session = cookieStore.get(COOKIE_NAME);
    return session?.value;
}

export async function deleteSession() {
    const cookieStore = await cookies();
    cookieStore.delete(COOKIE_NAME);
}
