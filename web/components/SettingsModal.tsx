'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Settings, X, Play, Loader2, Save } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Voice {
    name: string;
    ssmlGender: string;
}

interface UserSettings {
    germanVoice?: string;
    germanSpeed?: number;
    italianVoice?: string;
    italianSpeed?: number;
}

export function SettingsModal() {
    const [isOpen, setIsOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const [settings, setSettings] = useState<UserSettings | null>(null);

    // Voice Lists
    const [germanVoices, setGermanVoices] = useState<Voice[]>([]);
    const [italianVoices, setItalianVoices] = useState<Voice[]>([]);

    // Audio Playback
    const [playingSample, setPlayingSample] = useState<string | null>(null);

    // Fetch initial data when opened
    useEffect(() => {
        if (isOpen) {
            fetchSettings();
            fetchVoices('de-DE', setGermanVoices);
            fetchVoices('it-IT', setItalianVoices);
        }
    }, [isOpen]);

    const fetchSettings = async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/user/settings');
            if (res.ok) {
                const data = await res.json();
                setSettings(data);
            }
        } catch (e) {
            console.error("Failed to load settings", e);
        } finally {
            setLoading(false);
        }
    };

    const fetchVoices = async (lang: string, setter: (v: Voice[]) => void) => {
        try {
            const res = await fetch(`/api/tts/voices?languageCode=${lang}`);
            const data = await res.json();
            if (data.voices) setter(data.voices);
        } catch (e) {
            console.error(e);
        }
    };

    const handleSave = async () => {
        if (!settings) return;
        setLoading(true);
        try {
            await fetch('/api/user/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            setIsOpen(false);
        } catch (e) {
            console.error("Failed to save", e);
        } finally {
            setLoading(false);
        }
    };

    const updateSetting = (key: keyof UserSettings, value: string | number) => {
        setSettings(prev => prev ? ({ ...prev, [key]: value }) : { [key]: value });
    };

    const playSample = async (voiceName: string, langCode: string, speed: number = 1) => {
        if (playingSample) return;
        setPlayingSample(voiceName);

        const text = langCode === 'de-DE' ? 'Hallo, so klinge ich.' : 'Ciao, questa è la mia voce.';

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

    if (!isOpen) {
        return (
            <button
                onClick={() => setIsOpen(true)}
                className="fixed top-4 right-4 p-2 bg-white dark:bg-zinc-900 rounded-full shadow-lg border border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-all hover:scale-105 z-50"
                title="Global Settings"
            >
                <Settings className="w-6 h-6" />
            </button>
        );
    }

    return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
            <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl w-full max-w-lg border border-zinc-200 dark:border-zinc-800 flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-zinc-100 dark:border-zinc-800">
                    <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                        <Settings className="w-5 h-5" />
                        Voice Settings
                    </h2>
                    <button onClick={() => setIsOpen(false)} className="p-2 -mr-2 text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto space-y-8">
                    {loading && !settings ? (
                        <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 animate-spin text-zinc-400" /></div>
                    ) : (
                        <>
                            {/* German Settings */}
                            <div className="space-y-4">
                                <div className="flex items-center gap-2 text-sm font-semibold text-zinc-500 uppercase tracking-wider">
                                    <span className="w-2 h-2 rounded-full bg-orange-500" />
                                    German Voice
                                </div>
                                <div className="bg-zinc-50 dark:bg-zinc-800/50 p-4 rounded-xl space-y-4">
                                    <div className="flex gap-2">
                                        <select
                                            value={settings?.germanVoice || ''}
                                            onChange={(e) => updateSetting('germanVoice', e.target.value)}
                                            className="flex-1 p-2.5 rounded-lg border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm"
                                        >
                                            <option value="">Select Voice...</option>
                                            {germanVoices.map(v => (
                                                <option key={v.name} value={v.name}>{v.name.split('-').slice(2).join('-')} ({v.ssmlGender})</option>
                                            ))}
                                        </select>
                                        <button
                                            onClick={() => settings?.germanVoice && playSample(settings.germanVoice, 'de-DE', settings?.germanSpeed)}
                                            disabled={!settings?.germanVoice || playingSample !== null}
                                            className="p-2.5 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg hover:border-zinc-300 transition-colors disabled:opacity-50"
                                        >
                                            {playingSample === settings?.germanVoice ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
                                        </button>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className="text-sm text-zinc-500 w-12">Speed</span>
                                        <input
                                            type="range" min="0.5" max="2.0" step="0.25"
                                            value={settings?.germanSpeed || 1.0}
                                            onChange={(e) => updateSetting('germanSpeed', parseFloat(e.target.value))}
                                            className="flex-1 h-1.5 bg-zinc-200 dark:bg-zinc-700 rounded-lg appearance-none cursor-pointer"
                                        />
                                        <span className="text-sm font-mono text-zinc-600 dark:text-zinc-400 w-12 text-right">{settings?.germanSpeed || 1}x</span>
                                    </div>
                                </div>
                            </div>

                            {/* Italian Settings */}
                            <div className="space-y-4">
                                <div className="flex items-center gap-2 text-sm font-semibold text-zinc-500 uppercase tracking-wider">
                                    <span className="w-2 h-2 rounded-full bg-green-500" />
                                    Italian Voice
                                </div>
                                <div className="bg-zinc-50 dark:bg-zinc-800/50 p-4 rounded-xl space-y-4">
                                    <div className="flex gap-2">
                                        <select
                                            value={settings?.italianVoice || ''}
                                            onChange={(e) => updateSetting('italianVoice', e.target.value)}
                                            className="flex-1 p-2.5 rounded-lg border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-sm"
                                        >
                                            <option value="">Select Voice...</option>
                                            {italianVoices.map(v => (
                                                <option key={v.name} value={v.name}>{v.name.split('-').slice(2).join('-')} ({v.ssmlGender})</option>
                                            ))}
                                        </select>
                                        <button
                                            onClick={() => settings?.italianVoice && playSample(settings.italianVoice, 'it-IT', settings?.italianSpeed)}
                                            disabled={!settings?.italianVoice || playingSample !== null}
                                            className="p-2.5 bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg hover:border-zinc-300 transition-colors disabled:opacity-50"
                                        >
                                            {playingSample === settings?.italianVoice ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
                                        </button>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className="text-sm text-zinc-500 w-12">Speed</span>
                                        <input
                                            type="range" min="0.5" max="2.0" step="0.25"
                                            value={settings?.italianSpeed || 1.0}
                                            onChange={(e) => updateSetting('italianSpeed', parseFloat(e.target.value))}
                                            className="flex-1 h-1.5 bg-zinc-200 dark:bg-zinc-700 rounded-lg appearance-none cursor-pointer"
                                        />
                                        <span className="text-sm font-mono text-zinc-600 dark:text-zinc-400 w-12 text-right">{settings?.italianSpeed || 1}x</span>
                                    </div>
                                </div>
                            </div>

                        </>
                    )}
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-zinc-100 dark:border-zinc-800 flex justify-end gap-3">
                    <button
                        onClick={() => setIsOpen(false)}
                        className="px-4 py-2 text-sm font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={loading}
                        className="px-6 py-2 bg-zinc-900 hover:bg-zinc-800 text-white rounded-lg text-sm font-medium transition-colors shadow-sm flex items-center gap-2 disabled:opacity-70"
                    >
                        {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                        Save Settings
                    </button>
                </div>
            </div>
        </div>
    );
}
