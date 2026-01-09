import { TextToSpeechClient } from '@google-cloud/text-to-speech';
import { NextResponse } from 'next/server';

const client = new TextToSpeechClient({
    keyFilename: process.env.GOOGLE_APPLICATION_CREDENTIALS || process.cwd() + '/google-tts-key.json'
});

export async function POST(request: Request) {
    try {
        const { text, languageCode, voiceName, speakingRate } = await request.json();

        if (!text) {
            return NextResponse.json({ error: 'Text is required' }, { status: 400 });
        }

        const requestBody = {
            input: { text },
            // Select the language and SSML voice gender (optional)
            // If voiceName is provided, use it. Otherwise fall back to languageCode default.
            voice: voiceName
                ? { languageCode, name: voiceName }
                : { languageCode: languageCode || 'de-DE', ssmlGender: 'NEUTRAL' as const },
            // select the type of audio encoding
            audioConfig: {
                audioEncoding: 'MP3' as const,
                speakingRate: speakingRate || 1.0
            },
        };

        const [response] = await client.synthesizeSpeech(requestBody);
        const audioContent = response.audioContent;

        if (!audioContent) {
            return NextResponse.json({ error: 'No audio content received' }, { status: 500 });
        }

        // audioContent is a buffer (Uint8Array) or string. 
        // If it's a Buffer, we can return it as base64 string for easy client playback logic.
        const audioBase64 = Buffer.from(audioContent).toString('base64');

        return NextResponse.json({ audioContent: audioBase64 });

    } catch (error: any) {
        console.error('TTS API Error:', error);
        return NextResponse.json({ error: error.message || 'Internal Server Error' }, { status: 500 });
    }
}
