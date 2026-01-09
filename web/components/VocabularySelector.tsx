'use client';

import React, { useEffect, useState } from 'react';
import { Book, FileText, Loader2, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';

interface VocabularyFile {
    name: string;
    fileName: string;
    originalFile: string;
    count: number;
    lastModified: string;
}

interface VocabularySelectorProps {
    onSelect: (data: any[]) => void;
    onEdit: (fileName: string) => void;
}

export function VocabularySelector({ onSelect, onEdit }: VocabularySelectorProps) {
    const [files, setFiles] = useState<VocabularyFile[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedFile, setSelectedFile] = useState<string | null>(null);
    const [loadingFile, setLoadingFile] = useState(false);

    const fetchIndex = async () => {
        setLoading(true);
        setError(null);
        try {
            // Use the new API route instead of static file
            const res = await fetch('/api/vocabulary');
            if (!res.ok) throw new Error('Failed to load vocabulary index');
            const data = await res.json();
            setFiles(data);
        } catch (err) {
            console.error(err);
            setError('Could not load vocabulary list.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchIndex();
    }, []);

    const handleFileClick = async (file: VocabularyFile) => {
        if (loadingFile) return;
        setSelectedFile(file.fileName);
        setLoadingFile(true);

        try {
            // Load from API to ensure fresh data
            const res = await fetch(`/api/vocabulary/${file.fileName}`);
            if (!res.ok) throw new Error('Failed to load vocabulary file');
            const data = await res.json();
            onSelect(data);
        } catch (err) {
            console.error(err);
            alert('Failed to load the selected vocabulary file.');
            setSelectedFile(null);
        } finally {
            setLoadingFile(false);
        }
    };

    return (
        <div className="w-full max-w-2xl mx-auto space-y-6">
            <div className="text-center space-y-2">
                <h2 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
                    Select Vocabulary
                </h2>
                <p className="text-zinc-500 dark:text-zinc-400">
                    Choose a pre-loaded vocabulary set to start training.
                </p>
            </div>

            <div className="grid gap-4">
                {loading ? (
                    <div className="flex justify-center p-8">
                        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                    </div>
                ) : error ? (
                    <div className="text-center p-8 border border-red-200 rounded-lg bg-red-50 dark:bg-red-900/10 dark:border-red-900/50">
                        <p className="text-red-600 dark:text-red-400 mb-2">{error}</p>
                        <button
                            onClick={fetchIndex}
                            className="text-sm font-medium text-red-700 dark:text-red-300 hover:underline flex items-center justify-center gap-2 mx-auto"
                        >
                            <RefreshCw className="w-4 h-4" /> Try Again
                        </button>
                    </div>
                ) : files.length === 0 ? (
                    <div className="text-center p-8 border-2 border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl">
                        <p className="text-zinc-500 mb-4">No vocabulary files found.</p>
                        <button
                            onClick={fetchIndex}
                            className="text-sm text-blue-600 hover:underline"
                        >
                            Refresh
                        </button>
                    </div>
                ) : (
                    <div className="grid gap-3">
                        {files.map((file) => (
                            <div
                                key={file.fileName}
                                className={cn(
                                    "flex items-center justify-between p-4 rounded-xl border transition-all text-left bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 hover:border-blue-300 dark:hover:border-blue-700 hover:shadow-sm"
                                )}
                            >
                                <button
                                    onClick={() => handleFileClick(file)}
                                    disabled={loadingFile}
                                    className="flex-1 flex items-center gap-4 group"
                                >
                                    <div className={cn(
                                        "p-2 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-500 group-hover:text-blue-500 transition-colors"
                                    )}>
                                        <Book className="w-5 h-5" />
                                    </div>
                                    <div className="text-left">
                                        <h3 className="font-medium text-zinc-900 dark:text-zinc-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                                            {file.name}
                                        </h3>
                                        <p className="text-xs text-zinc-500 mt-0.5">
                                            {file.count} entries • {new Date(file.lastModified).toLocaleDateString()}
                                        </p>
                                    </div>
                                </button>

                                <div className="flex items-center gap-2 border-l border-zinc-100 dark:border-zinc-800 pl-4 ml-4">
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            onEdit(file.fileName);
                                        }}
                                        className="text-sm font-medium text-zinc-500 hover:text-blue-600 dark:hover:text-blue-400 px-3 py-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
                                    >
                                        Edit
                                    </button>
                                </div>

                                {selectedFile === file.fileName && loadingFile && (
                                    <div className="absolute inset-0 flex items-center justify-center bg-white/50 dark:bg-black/50 rounded-xl">
                                        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
