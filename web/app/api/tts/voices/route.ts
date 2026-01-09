import { TextToSpeechClient } from '@google-cloud/text-to-speech';
import { NextResponse } from 'next/server';

const client = new TextToSpeechClient({
    keyFilename: process.env.GOOGLE_APPLICATION_CREDENTIALS || process.cwd() + '/google-tts-key.json'
});

export async function GET(request: Request) {
    const { searchParams } = new URL(request.url);
    const languageCode = searchParams.get('languageCode');

    if (!languageCode) {
        return NextResponse.json({ error: 'Language code (languageCode) is required' }, { status: 400 });
    }

    try {
        const [result] = await client.listVoices({ languageCode });
        const voices = result.voices || [];

        // Return simplified voice objects
        const mappedVoices = voices.map(v => ({
            name: v.name,
            ssmlGender: v.ssmlGender,
            naturalSampleRateHertz: v.naturalSampleRateHertz
        }));

        return NextResponse.json({ voices: mappedVoices });
    } catch (error: any) {
        console.error("Error listing voices:", error);
        return NextResponse.json({ error: error.message || 'Internal Server Error' }, { status: 500 });
    }
}
