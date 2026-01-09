'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Card, checkAnswer, AnswerResult, normalizeAnswer } from '@/lib/trainer';
import { FeedbackDisplay } from './FeedbackDisplay';
import { Send, ArrowRight, Volume2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TTSSettings {
    code: string;
    voice?: string;
    speed?: number;
}

interface FlashcardProps {
    card: Card;
    deckCards: Card[]; // Needed for complex synonym checking
    onNext: () => void;
    // Stats (optional display)
    progress?: string;
    className?: string;
    ttsSettings?: TTSSettings;
    answerTts?: TTSSettings;
}

export function Flashcard({ card, deckCards, onNext, progress, className, ttsSettings, answerTts }: FlashcardProps) {
    const [input, setInput] = useState('');
    const [result, setResult] = useState<AnswerResult | null>(null);
    const [isPlaying, setIsPlaying] = useState(false);

    // Local TTS overrides for runtime adjustment
    const [localPromptTts, setLocalPromptTts] = useState<TTSSettings | undefined>(ttsSettings);
    const [localAnswerTts, setLocalAnswerTts] = useState<TTSSettings | undefined>(answerTts);

    // Sync local state if props change (though typically they are static during session)
    useEffect(() => { setLocalPromptTts(ttsSettings); }, [ttsSettings]);
    useEffect(() => { setLocalAnswerTts(answerTts); }, [answerTts]);

    const inputRef = useRef<HTMLInputElement>(null);

    // Focus input on mount and when card changes
    useEffect(() => {
        if (inputRef.current && !result) {
            inputRef.current.focus();
        }
    }, [card, result]);

    const handleSubmit = (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!input.trim()) return;

        if (!result) {
            // Check Answer
            const res = checkAnswer(input, card, deckCards);
            setResult(res);
        } else {
            // Next Card
            handleNext();
        }
    };

    const handleNext = () => {
        setResult(null);
        setInput('');
        onNext();
    };

    // Handle Enter key for "Next" when result is shown
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Enter' && result) {
                e.preventDefault(); // Prevent default form submission triggering a double next if focus is weird
                handleNext();
            }
        };
        if (result) {
            window.addEventListener('keydown', handleKeyDown);
        }
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [result, onNext]);

    const playAudio = async () => {
        // Use local overrides
        if (!localPromptTts?.code || isPlaying) return;

        try {
            setIsPlaying(true);
            const res = await fetch('/api/tts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: card.prompt,
                    languageCode: localPromptTts.code,
                    voiceName: localPromptTts.voice,
                    speakingRate: localPromptTts.speed
                })
            });

            const data = await res.json();
            if (data.audioContent) {
                const audio = new Audio(`data:audio/mp3;base64,${data.audioContent}`);
                audio.onended = () => setIsPlaying(false);
                audio.onerror = () => setIsPlaying(false);
                await audio.play();
            } else {
                setIsPlaying(false);
            }
        } catch (error) {
            console.error(error);
            setIsPlaying(false);
        }
    };

    // --- Voice Fetching for Runtime Settings ---
    const [availablePromptVoices, setAvailablePromptVoices] = useState<{ name: string, ssmlGender: string }[]>([]);
    const [availableAnswerVoices, setAvailableAnswerVoices] = useState<{ name: string, ssmlGender: string }[]>([]);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const settingsRef = useRef<HTMLDivElement>(null);

    // Close settings on click outside
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (settingsRef.current && !settingsRef.current.contains(event.target as Node)) {
                setSettingsOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // Fetch voices when settings open
    useEffect(() => {
        if (!settingsOpen) return;

        const fetchV = async (code: string, setter: any) => {
            try {
                const res = await fetch(`/api/tts/voices?languageCode=${code}`);
                const data = await res.json();
                if (data.voices) setter(data.voices);
            } catch (e) { console.error(e); }
        };

        if (localPromptTts?.code && availablePromptVoices.length === 0) fetchV(localPromptTts.code, setAvailablePromptVoices);
        if (localAnswerTts?.code && availableAnswerVoices.length === 0) fetchV(localAnswerTts.code, setAvailableAnswerVoices);

    }, [settingsOpen, localPromptTts?.code, localAnswerTts?.code]);

    const updateSettings = async (type: 'prompt' | 'answer', field: 'voice' | 'speed', value: string | number) => {
        let newSettings = type === 'prompt' ? { ...localPromptTts } : { ...localAnswerTts };

        // Update local state first for responsiveness
        if (type === 'prompt') {
            setLocalPromptTts(prev => prev ? ({ ...prev, [field]: value }) : { code: 'de-DE', [field]: value });
            newSettings = { ...localPromptTts, [field]: value } as TTSSettings;
            // Note: localPromptTts might be stale in this closure if we didn't use functional update for setLocal, 
            // but we need the *new* full object for the API call.
            // Better: construct new object cleanly.
        } else {
            setLocalAnswerTts(prev => prev ? ({ ...prev, [field]: value }) : { code: 'it-IT', [field]: value });
            newSettings = { ...localAnswerTts, [field]: value } as TTSSettings;
        }

        // Persist to server
        // We need to match the structure expected by consumers.
        // The users.json structure currently shows "settings": { "voice": ..., "speed": ... }. 
        // But we have split prompt/answer.
        // Let's adopt a structure: { prompt: { voice, speed }, answer: { voice, speed } }
        // OR flatten if we only really care about the "current language" voice?
        // User has explicit "Question (German)" and "Answer (Italian)".
        // It's safer to store `promptVoice`, `promptSpeed`, `answerVoice`, `answerSpeed`.

        const payload: any = {};
        if (type === 'prompt') {
            payload.promptVoice = field === 'voice' ? value : localPromptTts?.voice;
            payload.promptSpeed = field === 'speed' ? value : localPromptTts?.speed;
        } else {
            payload.answerVoice = field === 'voice' ? value : localAnswerTts?.voice;
            payload.answerSpeed = field === 'speed' ? value : localAnswerTts?.speed;
        }

        // Actually, to be safe, we should probably send what we have.
        // But `users.json` just had `voice` and `speed` before.
        // Let's migrate to `prompt` and `answer` nested keys or prefixed keys in `users.json`.
        // DeckConfig expects `voice` and `speed` for "generic" use? 
        // Let's see DeckConfig again.

        try {
            await fetch('/api/user/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
        } catch (e) {
            console.error("Failed to save settings", e);
        }
    };

    const [playingSample, setPlayingSample] = useState<string | null>(null);

    const playVoiceSample = async (voiceName: string, langCode: string, speed: number) => {
        if (playingSample) return;
        setPlayingSample(voiceName);

        // Simple localized sample texts
        const samples: Record<string, string> = {
            'de-DE': 'Hallo, so klinge ich.',
            'it-IT': 'Ciao, questa è la mia voce.',
            'en-US': 'Hello, this is my voice.',
            'fr-FR': 'Bonjour, voici ma voix.',
            'es-ES': 'Hola, esta es mi voz.'
        };

        const text = samples[langCode] || 'Test voice sample.';

        try {
            const res = await fetch('/api/tts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text,
                    languageCode: langCode,
                    voiceName,
                    speakingRate: speed
                })
            });
            const data = await res.json();
            if (data.audioContent) {
                const audio = new Audio(`data:audio/mp3;base64,${data.audioContent}`);
                audio.onended = () => setPlayingSample(null);
                audio.onerror = () => setPlayingSample(null);
                await audio.play();
            } else {
                setPlayingSample(null);
            }
        } catch (e) {
            console.error(e);
            setPlayingSample(null);
        }
    };

    return (
        <div className={cn("w-full max-w-4xl mx-auto flex flex-col min-h-[60vh]", className)}>

            {/* Top Bar: Progress & Title */}
            <div className="flex justify-between items-center text-sm text-zinc-400 mb-12 relative">
                <div className="font-medium tracking-wide">VOCITRAINER</div>

                {/* Runtime TTS Settings Trigger */}
                <div className="flex items-center gap-4 relative" ref={settingsRef}>
                    <button
                        onClick={() => setSettingsOpen(!settingsOpen)}
                        className={cn("p-2 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors", settingsOpen && "bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100")}
                        title="Voice Settings"
                    >
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.1a2 2 0 0 1-1-1.72v-.51a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" /><circle cx="12" cy="12" r="3" /></svg>
                    </button>

                    {settingsOpen && (
                        <div className="absolute top-full right-0 mt-2 w-72 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-xl p-4 z-50 text-left">
                            <h4 className="text-sm font-semibold mb-4 text-zinc-900 dark:text-zinc-100">Audio Settings</h4>

                            {/* Prompt Settings */}
                            {/* Prompt Settings */}
                            {localPromptTts && (
                                <div className="mb-4">
                                    <div className="flex justify-between mb-1">
                                        <label className="text-xs font-medium text-zinc-500 uppercase">
                                            {{ 'de-DE': 'German', 'it-IT': 'Italian', 'en-US': 'English', 'fr-FR': 'French', 'es-ES': 'Spanish' }[localPromptTts.code] || localPromptTts.code}
                                        </label>
                                    </div>
                                    <div className="flex items-center gap-2 mb-2">
                                        <select
                                            className="w-full text-sm p-2 rounded bg-zinc-50 dark:bg-zinc-800 border-none"
                                            value={localPromptTts.voice || ''}
                                            onChange={(e) => updateSettings('prompt', 'voice', e.target.value)}
                                        >
                                            <option value="">Default Voice</option>
                                            {availablePromptVoices.map(v => (
                                                <option key={v.name} value={v.name}>{v.name.split('-').slice(2).join('-')} ({v.ssmlGender})</option>
                                            ))}
                                        </select>
                                        <button
                                            onClick={() => localPromptTts.voice && playVoiceSample(localPromptTts.voice, localPromptTts.code, localPromptTts.speed || 1.0)}
                                            disabled={!localPromptTts.voice || playingSample !== null}
                                            className="p-2 rounded-full hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-500 transition-colors disabled:opacity-50"
                                            title="Play Sample"
                                        >
                                            {playingSample === localPromptTts.voice ? (
                                                <span className="block w-4 h-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                                            ) : (
                                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3" /></svg>
                                            )}
                                        </button>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs text-zinc-400">Speed:</span>
                                        <input
                                            type="range" min="0.5" max="2.0" step="0.25"
                                            value={localPromptTts.speed || 1.0}
                                            onChange={(e) => updateSettings('prompt', 'speed', parseFloat(e.target.value))}
                                            className="flex-1 h-1 bg-zinc-200 rounded-lg appearance-none cursor-pointer dark:bg-zinc-700"
                                        />
                                        <span className="text-xs font-mono w-8 text-right">{localPromptTts.speed || 1.0}x</span>
                                    </div>
                                </div>
                            )}

                            {/* Answer Settings */}
                            {localAnswerTts && (
                                <div className="pt-4 border-t border-zinc-100 dark:border-zinc-800">
                                    <label className="text-xs font-medium text-zinc-500 uppercase mb-1 block">
                                        {{ 'de-DE': 'German', 'it-IT': 'Italian', 'en-US': 'English', 'fr-FR': 'French', 'es-ES': 'Spanish' }[localAnswerTts.code] || localAnswerTts.code}
                                    </label>
                                    <div className="flex items-center gap-2 mb-2">
                                        <select
                                            className="w-full text-sm p-2 rounded bg-zinc-50 dark:bg-zinc-800 border-none"
                                            value={localAnswerTts.voice || ''}
                                            onChange={(e) => updateSettings('answer', 'voice', e.target.value)}
                                        >
                                            <option value="">Default Voice</option>
                                            {availableAnswerVoices.map(v => (
                                                <option key={v.name} value={v.name}>{v.name.split('-').slice(2).join('-')} ({v.ssmlGender})</option>
                                            ))}
                                        </select>
                                        <button
                                            onClick={() => localAnswerTts.voice && playVoiceSample(localAnswerTts.voice, localAnswerTts.code, localAnswerTts.speed || 1.0)}
                                            disabled={!localAnswerTts.voice || playingSample !== null}
                                            className="p-2 rounded-full hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-500 transition-colors disabled:opacity-50"
                                            title="Play Sample"
                                        >
                                            {playingSample === localAnswerTts.voice ? (
                                                <span className="block w-4 h-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                                            ) : (
                                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3" /></svg>
                                            )}
                                        </button>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs text-zinc-400">Speed:</span>
                                        <input
                                            type="range" min="0.5" max="2.0" step="0.25"
                                            value={localAnswerTts.speed || 1.0}
                                            onChange={(e) => updateSettings('answer', 'speed', parseFloat(e.target.value))}
                                            className="flex-1 h-1 bg-zinc-200 rounded-lg appearance-none cursor-pointer dark:bg-zinc-700"
                                        />
                                        <span className="text-xs font-mono w-8 text-right">{localAnswerTts.speed || 1.0}x</span>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <div>{progress}</div>
            </div>

            {/* Card Content */}
            <div className="flex-1 flex flex-col items-center">

                {/* Prompt */}
                <div className="w-full text-center space-y-4 mb-16">
                    <div className="text-zinc-500 text-lg uppercase tracking-wider font-medium">To Translate</div>
                    <div className="flex items-center justify-center gap-4">
                        <h1 className="text-5xl md:text-7xl font-bold text-zinc-900 dark:text-zinc-100 break-words leading-tight">
                            {card.prompt}
                            {card.pos_code && (
                                <span className="text-2xl md:text-3xl text-zinc-400 font-normal ml-3 align-top">
                                    [{card.pos_code}]
                                </span>
                            )}
                        </h1>
                        {localPromptTts?.code && (
                            <button
                                onClick={playAudio}
                                disabled={isPlaying}
                                className="p-2 rounded-full hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 disabled:opacity-50"
                                title="Play Audio"
                                type="button"
                            >
                                <Volume2 className={cn("w-8 h-8", isPlaying && "animate-pulse text-blue-500")} />
                            </button>
                        )}
                    </div>
                </div>

                {/* Interaction Area */}
                <div className="w-full max-w-xl relative group">
                    {!result ? (
                        /* Input Form */
                        <form onSubmit={handleSubmit} className="relative">
                            <input
                                ref={inputRef}
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder="Type answer..."
                                className="w-full bg-transparent border-b-2 border-zinc-200 dark:border-zinc-800 text-3xl md:text-4xl py-4 px-2 text-center outline-none focus:border-black dark:focus:border-white transition-colors placeholder:text-zinc-200 dark:placeholder:text-zinc-800"
                                autoComplete="off"
                                autoCorrect="off"
                                autoCapitalize="off"
                                spellCheck="false"
                            />
                            <button
                                type="submit"
                                disabled={!input.trim()}
                                className="absolute right-0 top-1/2 -translate-y-1/2 p-3 text-zinc-300 hover:text-zinc-900 dark:hover:text-white transition-colors disabled:opacity-0"
                            >
                                <Send className="w-6 h-6" />
                            </button>
                            <div className="text-center mt-4 text-zinc-400 text-sm">Press Enter to check</div>
                        </form>
                    ) : (
                        /* Result Action (Next) - visual cue only, keyboard handles it mostly */
                        <button
                            onClick={handleNext}
                            className="w-full flex items-center justify-center space-x-2 py-4 bg-zinc-900 hover:bg-zinc-800 text-white rounded-xl transition-all shadow-lg hover:shadow-xl"
                        >
                            <span>Next Card</span>
                            <ArrowRight className="w-5 h-5" />
                        </button>
                    )}
                </div>

                {/* Feedback Section */}
                {result && (
                    <FeedbackDisplay card={card} result={result} userAnswer={input} ttsSettings={localAnswerTts} />
                )}

            </div>
        </div>
    );
}
