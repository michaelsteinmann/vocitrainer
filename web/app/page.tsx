'use client';

import React, { useState } from 'react';
import { parseExcelFile, buildDeck, Card } from '@/lib/trainer';
import { FileUpload } from '@/components/FileUpload';
import { DeckConfig, DeckConfig as IDeckConfig } from '@/components/DeckConfig';
import { Flashcard } from '@/components/Flashcard';
import { Shuffle } from 'lucide-react';

export default function Home() {
  const [step, setStep] = useState<'upload' | 'config' | 'training'>('upload');

  // Data State
  const [rawData, setRawData] = useState<any[]>([]);
  const [columns, setColumns] = useState<string[]>([]);

  // Deck State
  const [deck, setDeck] = useState<Card[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  // Handlers
  const handleFileSelect = async (file: File) => {
    try {
      const data = await parseExcelFile(file);
      if (data.length > 0) {
        setRawData(data);
        setColumns(Object.keys(data[0]));
        setStep('config');
      } else {
        alert("File seems empty or invalid.");
      }
    } catch (e) {
      console.error(e);
      alert("Error parsing file.");
    }
  };

  const handleConfigConfirm = (config: IDeckConfig) => {
    const cards = buildDeck(
      rawData,
      config.promptCol,
      config.answerCols,
      config.filters,
      config.reverse
    );

    // Shuffle the deck (simple shuffle)
    const shuffled = [...cards].sort(() => Math.random() - 0.5);

    setDeck(shuffled);
    setCurrentIndex(0);
    setStep('training');
  };

  const handleNextCard = () => {
    // Basic cycling for now. 
    // Ideally we'd remove correct cards or have a spaced repetition logic,
    // but the python app just cycles or reinserts.
    // For MVP: Simple cycle.
    if (currentIndex < deck.length - 1) {
      setCurrentIndex(prev => prev + 1);
    } else {
      // End of deck
      // Reshuffle or restart?
      const doRestart = confirm("End of deck! Restart?");
      if (doRestart) {
        setDeck(prev => [...prev].sort(() => Math.random() - 0.5));
        setCurrentIndex(0);
      } else {
        setStep('upload');
      }
    }
  };

  return (
    <main className="min-h-screen bg-white dark:bg-black font-sans text-zinc-900 dark:text-zinc-100 selection:bg-blue-100 dark:selection:bg-blue-900">
      <div className="container mx-auto px-4 py-8 md:py-12 lg:py-16">

        {step === 'upload' && (
          <div className="max-w-2xl mx-auto animate-in fade-in zoom-in duration-500">
            <h1 className="text-4xl font-bold text-center mb-12 tracking-tight">Vocitrainer</h1>
            <FileUpload onFileSelect={handleFileSelect} />
          </div>
        )}

        {step === 'config' && (
          <DeckConfig
            columns={columns}
            totalRows={rawData.length}
            onConfirm={handleConfigConfirm}
          />
        )}

        {step === 'training' && deck.length > 0 && (
          <Flashcard
            card={deck[currentIndex]}
            deckCards={deck}
            onNext={handleNextCard}
            progress={`${currentIndex + 1} / ${deck.length}`}
          />
        )}

      </div>
    </main>
  );
}
