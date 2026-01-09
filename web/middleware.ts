import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
    const session = request.cookies.get('auth_session');

    // Public paths that don't require authentication
    const publicPaths = ['/login', '/favicon.ico', '/api/auth/login'];
    const isPublicPath = publicPaths.some(path => request.nextUrl.pathname.startsWith(path)) ||
        request.nextUrl.pathname.startsWith('/_next');

    if (!session && !isPublicPath) {
        return NextResponse.redirect(new URL('/login', request.url));
    }

    if (session && request.nextUrl.pathname === '/login') {
        return NextResponse.redirect(new URL('/', request.url));
    }

    return NextResponse.next();
}

export const config = {
    matcher: [
        '/((?!api|_next/static|_next/image|favicon.ico).*)',
    ],
};
