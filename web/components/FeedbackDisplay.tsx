'use client';

import React from 'react';
import { Card, AnswerResult } from '@/lib/trainer';
import { cn } from '@/lib/utils';
import { BookOpen, Languages, Sparkles } from 'lucide-react';

interface FeedbackDisplayProps {
    card: Card;
    result: AnswerResult;
    userAnswer: string;
    ttsSettings?: {
        code: string;
        voice?: string;
        speed?: number;
    };
}

export function FeedbackDisplay({ card, result, userAnswer, ttsSettings }: FeedbackDisplayProps) {
    const playAnswerAudio = async () => {
        if (!ttsSettings?.code) return;
        try {
            // Find the correct answer text - typically one of the answers match but we should play the 'primary' correct answer
            // Simplification: Play the first accepted answer (usually the canonical one if available, but here deck structure has 'answers' array implied from col)
            // The card object doesn't have 'answers' array directly in interface Card?
            // Actually 'checkAnswer' uses dynamic columns.
            // But we know 'card' has key-values.
            // Wait, card object has normalized keys or original keys?
            // The result.feedback usually contains the correct answer if wrong.
            // If correct, userAnswer is correct.
            // Let's rely on `card['...']`. 
            // Better: `result.feedback` often says "Correct Answer: X".
            // But we want to play the Clean answer.
            // If result.correctAnswers is available? `AnswerResult` has `correctAnswers`?
            // Let's check checkAnswer return type or just use a best guess (e.g. `card[answerCols[0]]`).
            // Actually `FeedbackDisplay` doesn't know answer cols.
            // BUT, `result` structure might help.
            // If I look at `lib/trainer.ts`, `AnswerResult` has `feedback`.
            // Let's just use `card[Object.keys(card).find(k => k.toLowerCase().includes('italien')) || '']`? Risky.
            // Or just play what the user agreed was correct?
            // If I can't find the text, I can't play it.
            // The user wants audio for the Answer.
            // The `card` has all data.
            // Maybe I should pass the `answerText` to FeedbackDisplay?
            // But `FeedbackDisplay` is generic.
            // Let's assume for now we use `userAnswer` if correct, or `result.feedback` (parsed) if wrong?
            // "Correct Answer: <text>"
            // This is messy.
            // Let's look at `Flashcard` -> `checkAnswer` -> `result`.
            // `checkAnswer` returns `{ isCorrect, status, feedback }`.
            // It does NOT return the canonical answer text explicitly in a field.
            // I should probably fix `checkAnswer` or `Flashcard` to pass the correct answer text.

            // For now, I'll assume we can't easily play it unless I know the column. 
            // BUT, in `DeckConfig`, we know `answerCols`.
            // `page.tsx` builds `deck`. `Card` has specific structure?
            // `Card` is `{ prompt: string, ...rest }`.
            // Wait, `buildDeck` extracts `prompt` and `answer`?
            // Let's check `lib/trainer.ts`.
            // If `Card` has `answers` array?
        } catch (e) { console.error(e); }
    };

    // RE-EVALUATION: `FeedbackDisplay` needs the text to play.
    // I really need to check `lib/trainer.ts` to see what `Card` looks like or `AnswerResult`.

    // HOLD OFF writing until I check `lib/trainer.ts`.
    // Returning original content for now to not break it while I check tool output.
    return (
        <div className="w-full max-w-2xl mx-auto mt-8 animate-in fade-in slide-in-from-bottom-2 duration-300">

            {/* Primary Feedback Banner */}
            <div className={cn(
                "p-6 rounded-xl text-center mb-8 border-l-4 shadow-sm relative",
                result.status === 'correct' && "bg-green-50 text-green-800 border-green-500 dark:bg-green-900/20 dark:text-green-300",
                result.status === 'synonym' && "bg-yellow-50 text-yellow-800 border-yellow-500 dark:bg-yellow-900/20 dark:text-yellow-300",
                result.status === 'wrong' && "bg-red-50 text-red-800 border-red-500 dark:bg-red-900/20 dark:text-red-300",
            )}>
                <h3 className="text-2xl font-bold mb-2 flex items-center justify-center gap-2">
                    {result.status === 'correct' && <span className="text-3xl">●</span>}
                    {result.status === 'synonym' && <span className="text-3xl">◑</span>}
                    {result.status === 'wrong' && <span className="text-3xl">○</span>}
                    <span>{result.feedback}</span>
                </h3>
                {/* Audio Button for Answer (if we can find the text) */}
                {/* ... implementation pending verification of text source ... */}

                {/* Explanation displayed prominently if correct */}
                {result.isCorrect && card.explanation && (
                    <p className="mt-2 text-zinc-600 dark:text-zinc-400 font-medium">
                        {card.explanation}
                    </p>
                )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

                {/* Left Column: Examples & Explanations */}
                <div className="space-y-6">
                    {(card.example || card.german_example) && (
                        <div className="bg-white dark:bg-zinc-900 p-5 rounded-lg border border-zinc-200 dark:border-zinc-800">
                            <h4 className="flex items-center text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                                <BookOpen className="w-4 h-4 mr-2" /> Examples
                            </h4>
                            {card.example && (
                                <p className="text-lg italic text-zinc-800 dark:text-zinc-200 mb-2 font-serif">
                                    "{card.example}"
                                </p>
                            )}
                            {card.german_example && (
                                <p className="text-zinc-500 dark:text-zinc-400 italic">
                                    {card.german_example}
                                </p>
                            )}
                        </div>
                    )}

                    {/* If wrong, show explanation here if not shown above */}
                    {!result.isCorrect && card.explanation && (
                        <div className="bg-white dark:bg-zinc-900 p-5 rounded-lg border border-zinc-200 dark:border-zinc-800">
                            <h4 className="flex items-center text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                                <Sparkles className="w-4 h-4 mr-2" /> Explanation
                            </h4>
                            <p className="text-zinc-700 dark:text-zinc-300">
                                {card.explanation}
                            </p>
                        </div>
                    )}
                </div>

                {/* Right Column: Synonyms & Grammar */}
                <div className="space-y-6">
                    {/* Show German Synonyms if available (and prompt was Italian/Foreign) */}
                    {/* OR if prompt was German, show other Italian variants if we had them (not implemented in MVP fully yet) */}
                    {/* For now, just show german_synonyms if present */}
                    {(card.german_synonyms && card.german_synonyms.length > 0) && (
                        <div className="bg-white dark:bg-zinc-900 p-5 rounded-lg border border-zinc-200 dark:border-zinc-800">
                            <h4 className="flex items-center text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                                <Languages className="w-4 h-4 mr-2" /> Synonyms (De)
                            </h4>
                            <ul className="space-y-1">
                                {card.german_synonyms.map((syn, i) => (
                                    <li key={i} className="text-zinc-700 dark:text-zinc-300 pl-4 border-l-2 border-zinc-100 dark:border-zinc-800">
                                        {syn}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Show Grammar codes if available */}
                    {card.pos_code && (
                        <div className="bg-zinc-50 dark:bg-zinc-900/50 p-4 rounded-lg">
                            <span className="text-xs font-mono text-zinc-400 uppercase">POS</span>
                            <span className="ml-2 font-medium text-zinc-700 dark:text-zinc-300">{card.pos_code}</span>
                        </div>
                    )}
                </div>

            </div>

        </div>
    );
}
