'use client';

import React, { useCallback } from 'react';
import { Upload, FileUp } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FileUploadProps {
    onFileSelect: (file: File) => void;
}

export function FileUpload({ onFileSelect }: FileUploadProps) {
    const [isDragOver, setIsDragOver] = React.useState(false);

    const handleDrop = useCallback(
        (e: React.DragEvent<HTMLDivElement>) => {
            e.preventDefault();
            setIsDragOver(false);
            const file = e.dataTransfer.files[0];
            if (file && (file.name.endsWith('.xlsx') || file.name.endsWith('.csv'))) {
                onFileSelect(file);
            }
        },
        [onFileSelect]
    );

    const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragOver(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragOver(false);
    }, []);

    return (
        <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={cn(
                "flex flex-col items-center justify-center p-12 border-2 border-dashed rounded-xl transition-colors cursor-pointer min-h-[400px]",
                isDragOver
                    ? "border-blue-500 bg-blue-50/10"
                    : "border-zinc-300 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-600"
            )}
        >
            <div className="p-4 rounded-full bg-zinc-100 dark:bg-zinc-800 mb-6">
                <FileUp className="w-10 h-10 text-zinc-500" />
            </div>
            <h3 className="text-xl font-semibold mb-2 text-center text-zinc-900 dark:text-zinc-100">
                Upload Vocabulary File
            </h3>
            <p className="text-zinc-500 dark:text-zinc-400 text-center mb-6 max-w-sm">
                Drag and drop your Excel (.xlsx) or CSV file here, or click to browse.
            </p>

            <label className="relative">
                <input
                    type="file"
                    className="hidden"
                    accept=".xlsx,.xls,.csv"
                    onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) onFileSelect(file);
                    }}
                />
                <span className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors shadow-sm">
                    Browse Files
                </span>
            </label>
        </div>
    );
}
