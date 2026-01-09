'use client';

import React, { useState, useEffect } from 'react';
import { ArrowRightLeft, Check, Settings2, Play, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DeckConfigProps {
    columns: string[];
    totalRows: number;
    onConfirm: (config: DeckConfig) => void;
}

export interface DeckConfig {
    promptCol: string;
    answerCols: string[];
    reverse: boolean;
    filters: {
        niveaus: string[];
        frequency: string[];
    };
    languages: {
        prompt: { code: string, voice?: string, speed?: number };
        answer: { code: string, voice?: string, speed?: number };
    };
}

interface Voice {
    name: string;
    ssmlGender: string;
}

const NIVEAUS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
const FREQUENCIES = ['1', '2', '3', '4', '5'];
const SUPPORTED_LANGS = [
    { code: 'de-DE', name: 'German' },
    { code: 'it-IT', name: 'Italian' },
    { code: 'en-US', name: 'English' },
    { code: 'fr-FR', name: 'French' },
    { code: 'es-ES', name: 'Spanish' },
];

export function DeckConfig({ columns, totalRows, onConfirm }: DeckConfigProps) {
    const [promptCol, setPromptCol] = useState<string>(columns[0] || '');
    const [answerCols, setAnswerCols] = useState<string[]>([]);
    const [reverse, setReverse] = useState(false);
    const [selectedNiveaus, setSelectedNiveaus] = useState<string[]>(NIVEAUS);
    const [selectedFreqs, setSelectedFreqs] = useState<string[]>(FREQUENCIES);

    // Detailed Language State
    const [promptLang, setPromptLang] = useState('de-DE');
    const [promptVoice, setPromptVoice] = useState<string>('');
    const [promptSpeed, setPromptSpeed] = useState<number>(1.0);
    const [promptVoices, setPromptVoices] = useState<Voice[]>([]);

    const [answerLang, setAnswerLang] = useState('it-IT');
    const [answerVoice, setAnswerVoice] = useState<string>('');
    const [answerSpeed, setAnswerSpeed] = useState<number>(1.0);
    const [answerVoices, setAnswerVoices] = useState<Voice[]>([]);

    const [playingSample, setPlayingSample] = useState<string | null>(null);

    const playSample = async (voiceName: string, langCode: string, speed: number) => {
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



    // User Settings State
    const [userSettings, setUserSettings] = useState<{ voice?: string, speed?: number } | null>(null);

    // Fetch User Settings
    useEffect(() => {
        fetch('/api/user/settings')
            .then(res => {
                if (res.ok) return res.json();
                return null;
            })
            .then(settings => {
                if (settings) {
                    setUserSettings(settings);
                    // Apply speed globally if set
                    if (settings.speed) {
                        setPromptSpeed(settings.speed);
                        setAnswerSpeed(settings.speed);
                    }
                }
            })
            .catch(err => console.error("Failed to load user settings", err));
    }, []);

    // Apply User Voice Setting when Language Matches
    useEffect(() => {
        if (userSettings?.voice && promptLang && userSettings.voice.startsWith(promptLang)) {
            setPromptVoice(userSettings.voice);
        }
    }, [promptLang, userSettings]);

    useEffect(() => {
        if (userSettings?.voice && answerLang && userSettings.voice.startsWith(answerLang)) {
            setAnswerVoice(userSettings.voice);
        }
    }, [answerLang, userSettings]);

    // Fetch voices helper
    const fetchVoices = async (langCode: string, setter: (v: Voice[]) => void) => {
        try {
            const res = await fetch(`/api/tts/voices?languageCode=${langCode}`);
            const data = await res.json();
            if (data.voices) {
                setter(data.voices);
            } else {
                setter([]);
            }
        } catch (e) {
            console.error("Failed to fetch voices", e);
            setter([]);
        }
    };

    // Effect: Fetch voices when language changes
    useEffect(() => {
        fetchVoices(promptLang, setPromptVoices);
        setPromptVoice(''); // Reset selection on lang change
    }, [promptLang]);

    useEffect(() => {
        fetchVoices(answerLang, setAnswerVoices);
        setAnswerVoice('');
    }, [answerLang]);


    // Auto-detect defaults
    useEffect(() => {
        const deCols = columns.filter(c => c.toLowerCase().startsWith('deutsch'));
        const itCols = columns.filter(c => c.toLowerCase().startsWith('italien'));

        if (itCols.length > 0) setPromptCol(itCols[0]);
        else if (columns.length > 0) setPromptCol(columns[0]);

        if (deCols.length > 0) setAnswerCols(deCols);
    }, [columns]);



    const handleSubmit = () => {
        if (!promptCol || answerCols.length === 0) return;
        onConfirm({
            promptCol,
            answerCols,
            reverse,
            filters: {
                niveaus: selectedNiveaus,
                frequency: selectedFreqs
            },
            languages: {
                prompt: { code: promptLang, voice: promptVoice, speed: promptSpeed },
                answer: { code: answerLang, voice: answerVoice, speed: answerSpeed }
            }
        });
    };

    const toggleAnswerCol = (col: string) => {
        setAnswerCols(prev =>
            prev.includes(col) ? prev.filter(c => c !== col) : [...prev, col]
        );
    };

    const toggleArrayItem = (item: string, current: string[], setter: (v: string[]) => void) => {
        setter(current.includes(item) ? current.filter(i => i !== item) : [...current, item]);
    };

    const renderVoiceControls = (
        voices: Voice[],
        currentVoice: string,
        setVoice: (v: string) => void,
        currentSpeed: number,
        setSpeed: (s: number) => void,
        langCode: string
    ) => {
        if (voices.length === 0) return null;

        return (
            <div className="mt-2 flex items-center gap-3">
                <select
                    value={currentVoice}
                    onChange={(e) => setVoice(e.target.value)}
                    className="p-1.5 rounded border border-zinc-300 dark:border-zinc-700 text-xs bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 max-w-[180px] shadow-sm"
                >
                    <option value="">Default Voice</option>
                    {voices.map(v => (
                        <option key={v.name} value={v.name}>{v.name.split('-').slice(2).join('-')} ({v.ssmlGender})</option>
                    ))}
                </select>

                <div className="flex items-center gap-1">
                    <span className="text-xs text-zinc-400">Rate:</span>
                    <select
                        value={currentSpeed}
                        onChange={(e) => setSpeed(parseFloat(e.target.value))}
                        className="p-1.5 rounded border border-zinc-300 dark:border-zinc-700 text-xs bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-sm"
                    >
                        {[0.5, 0.75, 1.0, 1.25, 1.5, 2.0].map(r => (
                            <option key={r} value={r}>{r}x</option>
                        ))}
                    </select>
                </div>

                {currentVoice && (
                    <button
                        onClick={() => playSample(currentVoice, langCode, currentSpeed)}
                        disabled={playingSample !== null}
                        className="p-1.5 rounded-full hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors disabled:opacity-50"
                        title="Play Sample"
                    >
                        {playingSample === currentVoice ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                    </button>
                )}
            </div>
        );
    };

    return (
        <div className="max-w-4xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">

            <div className="flex items-center space-x-4 mb-8">
                <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg text-blue-600 dark:text-blue-400">
                    <Settings2 className="w-6 h-6" />
                </div>
                <div>
                    <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Configure Training</h2>
                    <p className="text-zinc-500 dark:text-zinc-400">Select columns and filters for your session.</p>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Column Selection */}
                <div className="space-y-6 bg-white dark:bg-zinc-900 p-6 rounded-xl border border-zinc-200 dark:border-zinc-800 shadow-sm">
                    <h3 className="font-semibold text-lg flex items-center space-x-2">
                        <span>Column Mapping</span>
                    </h3>

                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                                Prompt (Question)
                            </label>
                            <select
                                value={promptCol}
                                onChange={(e) => setPromptCol(e.target.value)}
                                className="w-full p-2.5 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 shadow-sm"
                            >
                                {columns.map(c => (
                                    <option key={c} value={c}>{c}</option>
                                ))}
                            </select>


                        </div>

                        <div className="flex justify-center py-2">
                            <button
                                onClick={() => setReverse(!reverse)}
                                className={cn(
                                    "p-2 rounded-full transition-colors flex items-center space-x-2 text-sm font-medium",
                                    reverse ? "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300" : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400 hover:bg-zinc-200"
                                )}
                            >
                                <ArrowRightLeft className="w-4 h-4" />
                                <span>Reverse Direction: {reverse ? 'ON' : 'OFF'}</span>
                            </button>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                                Answers (Select multiple)
                            </label>
                            <div className="max-h-48 overflow-y-auto space-y-1 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2">
                                {columns.filter(c => c !== promptCol).map(col => (
                                    <div
                                        key={col}
                                        onClick={() => toggleAnswerCol(col)}
                                        className={cn(
                                            "flex items-center space-x-3 p-2 rounded cursor-pointer transition-colors",
                                            answerCols.includes(col) ? "bg-blue-50 dark:bg-blue-900/20" : "hover:bg-zinc-50 dark:hover:bg-zinc-800"
                                        )}
                                    >
                                        <div className={cn(
                                            "w-4 h-4 rounded border flex items-center justify-center",
                                            answerCols.includes(col) ? "bg-blue-500 border-blue-500" : "border-zinc-400"
                                        )}>
                                            {answerCols.includes(col) && <Check className="w-3 h-3 text-white" />}
                                        </div>
                                        <span className="text-sm">{col}</span>
                                    </div>
                                ))}
                            </div>

                            {/* Language Selector for Answer - REMOVED Language Dropdown (Fixed to Italian) */}
                            <div className="mt-2 flex flex-col gap-2">
                                {renderVoiceControls(answerVoices, answerVoice, setAnswerVoice, answerSpeed, setAnswerSpeed, answerLang)}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Filters */}
                <div className="space-y-6 bg-white dark:bg-zinc-900 p-6 rounded-xl border border-zinc-200 dark:border-zinc-800 shadow-sm">
                    <h3 className="font-semibold text-lg">Filters</h3>

                    <div>
                        <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                            Difficulty Level
                        </label>
                        <div className="flex flex-wrap gap-2">
                            {NIVEAUS.map(lvl => (
                                <button
                                    key={lvl}
                                    onClick={() => toggleArrayItem(lvl, selectedNiveaus, setSelectedNiveaus)}
                                    className={cn(
                                        "px-3 py-1.5 rounded-md text-sm font-medium transition-all border",
                                        selectedNiveaus.includes(lvl)
                                            ? "bg-zinc-900 text-white border-zinc-900 dark:bg-zinc-100 dark:text-zinc-900"
                                            : "text-zinc-500 border-zinc-200 hover:border-zinc-300 dark:border-zinc-800 dark:text-zinc-400"
                                    )}
                                >
                                    {lvl}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                            Frequency (1=Frequent, 5=Rare)
                        </label>
                        <div className="flex flex-wrap gap-2">
                            {FREQUENCIES.map(f => (
                                <button
                                    key={f}
                                    onClick={() => toggleArrayItem(f, selectedFreqs, setSelectedFreqs)}
                                    className={cn(
                                        "w-8 h-8 flex items-center justify-center rounded-md text-sm font-medium transition-all border",
                                        selectedFreqs.includes(f)
                                            ? "bg-blue-600 text-white border-blue-600"
                                            : "text-zinc-500 border-zinc-200 hover:border-zinc-300 dark:border-zinc-800"
                                    )}
                                >
                                    {f}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="pt-6 border-t border-zinc-100 dark:border-zinc-800 mt-auto">
                        <div className="text-sm text-zinc-500">
                            Source contains {totalRows} total rows. Filters will apply at start.
                        </div>
                    </div>
                </div>
            </div>

            <div className="flex justify-end pt-4">
                <button
                    onClick={handleSubmit}
                    disabled={!promptCol || answerCols.length === 0}
                    className="px-8 py-3 bg-zinc-900 hover:bg-zinc-800 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    Start Training
                </button>
            </div>
        </div>
    );
}
