'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Card, checkAnswer, AnswerResult, normalizeAnswer } from '@/lib/trainer';
import { FeedbackDisplay } from './FeedbackDisplay';
import { Send, ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FlashcardProps {
    card: Card;
    deckCards: Card[]; // Needed for complex synonym checking
    onNext: () => void;
    // Stats (optional display)
    progress?: string;
    className?: string;
}

export function Flashcard({ card, deckCards, onNext, progress, className }: FlashcardProps) {
    const [input, setInput] = useState('');
    const [result, setResult] = useState<AnswerResult | null>(null);
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
    }, [result, onNext]); // Dependencies must be precise

    return (
        <div className={cn("w-full max-w-4xl mx-auto flex flex-col min-h-[60vh]", className)}>

            {/* Top Bar: Progress & Title */}
            <div className="flex justify-between items-center text-sm text-zinc-400 mb-12">
                <div className="font-medium tracking-wide">VOCITRAINER WEB</div>
                <div>{progress}</div>
            </div>

            {/* Card Content */}
            <div className="flex-1 flex flex-col items-center">

                {/* Prompt */}
                <div className="w-full text-center space-y-4 mb-16">
                    <div className="text-zinc-500 text-lg uppercase tracking-wider font-medium">To Translate</div>
                    <h1 className="text-5xl md:text-7xl font-bold text-zinc-900 dark:text-zinc-100 break-words leading-tight">
                        {card.prompt}
                        {card.pos_code && (
                            <span className="text-2xl md:text-3xl text-zinc-400 font-normal ml-3 align-top">
                                [{card.pos_code}]
                            </span>
                        )}
                    </h1>
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
                    <FeedbackDisplay card={card} result={result} userAnswer={input} />
                )}

            </div>
        </div>
    );
}
