'use client';

import React, { useState, useEffect } from 'react';
import { Save, Plus, Trash2, ArrowLeft, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface VocabularyEditorProps {
    fileName: string;
    onBack: () => void;
}

export function VocabularyEditor({ fileName, onBack }: VocabularyEditorProps) {
    const [data, setData] = useState<any[]>([]);
    const [columns, setColumns] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadFile();
    }, [fileName]);

    const loadFile = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`/api/vocabulary/${fileName}`);
            if (!res.ok) throw new Error('Failed to load file');
            const jsonData = await res.json();

            if (Array.isArray(jsonData) && jsonData.length > 0) {
                setData(jsonData);
                // Extract all possible keys from all objects to form columns
                const allKeys = new Set<string>();
                jsonData.forEach(row => Object.keys(row).forEach(k => allKeys.add(k)));
                setColumns(Array.from(allKeys));
            } else if (Array.isArray(jsonData) && jsonData.length === 0) {
                setData([]);
                setColumns(['Deutsch', 'Fremdsprache']); // Default columns for empty file
            } else {
                throw new Error('Invalid file format');
            }
        } catch (err) {
            console.error(err);
            setError('Could not load vocabulary data.');
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            const res = await fetch(`/api/vocabulary/${fileName}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            if (!res.ok) throw new Error('Failed to save');
            alert('File saved successfully!');
        } catch (err) {
            console.error(err);
            alert('Failed to save changes.');
        } finally {
            setSaving(false);
        }
    };

    const handleCellChange = (rowIndex: number, col: string, value: string) => {
        const newData = [...data];
        if (!newData[rowIndex]) newData[rowIndex] = {};
        newData[rowIndex] = { ...newData[rowIndex], [col]: value };
        setData(newData);
    };

    const addRow = () => {
        const newRow: any = {};
        columns.forEach(c => newRow[c] = '');
        setData([...data, newRow]);
    };

    const deleteRow = (index: number) => {
        if (confirm('Are you sure you want to delete this row?')) {
            setData(data.filter((_, i) => i !== index));
        }
    };

    const addColumn = () => {
        const name = prompt('Enter new column name:');
        if (name && !columns.includes(name)) {
            setColumns([...columns, name]);
        }
    };

    if (loading) {
        return (
            <div className="flex justify-center p-12">
                <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="text-center p-8 text-red-600">
                <p>{error}</p>
                <button onClick={onBack} className="mt-4 underline">Go Back</button>
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in zoom-in duration-500">
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button
                        onClick={onBack}
                        className="p-2 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-full transition-colors"
                    >
                        <ArrowLeft className="w-6 h-6" />
                    </button>
                    <div>
                        <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
                            Editing: {fileName}
                        </h2>
                        <p className="text-sm text-zinc-500">{data.length} entries</p>
                    </div>
                </div>

                <div className="flex gap-2">
                    <button
                        onClick={addRow}
                        className="flex items-center gap-2 px-4 py-2 text-zinc-700 bg-white border border-zinc-200 hover:bg-zinc-50 rounded-lg text-sm font-medium transition-colors dark:bg-zinc-800 dark:border-zinc-700 dark:text-zinc-200"
                    >
                        <Plus className="w-4 h-4" /> Add Row
                    </button>
                    <button
                        onClick={addColumn}
                        className="flex items-center gap-2 px-4 py-2 text-zinc-700 bg-white border border-zinc-200 hover:bg-zinc-50 rounded-lg text-sm font-medium transition-colors dark:bg-zinc-800 dark:border-zinc-700 dark:text-zinc-200"
                    >
                        <Plus className="w-4 h-4" /> Add Column
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium shadow-sm transition-colors disabled:opacity-50"
                    >
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        Save Changes
                    </button>
                </div>
            </div>

            <div className="overflow-x-auto border border-zinc-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-900 shadow-sm">
                <table className="w-full text-sm text-left">
                    <thead className="text-xs text-zinc-500 uppercase bg-zinc-50 dark:bg-zinc-800/50 border-b border-zinc-200 dark:border-zinc-800">
                        <tr>
                            <th className="px-4 py-3 w-12 text-center">#</th>
                            {columns.map(col => (
                                <th key={col} className="px-4 py-3 font-medium tracking-wider">
                                    {col}
                                </th>
                            ))}
                            <th className="px-4 py-3 w-10"></th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                        {data.map((row, rowIndex) => (
                            <tr key={rowIndex} className="hover:bg-blue-50/50 dark:hover:bg-blue-900/10 group">
                                <td className="px-4 py-3 text-center text-zinc-400 text-xs">
                                    {rowIndex + 1}
                                </td>
                                {columns.map(col => (
                                    <td key={`${rowIndex}-${col}`} className="p-0">
                                        <input
                                            type="text"
                                            value={row[col] || ''}
                                            onChange={(e) => handleCellChange(rowIndex, col, e.target.value)}
                                            className="w-full px-4 py-3 bg-transparent border-none focus:ring-1 focus:ring-inset focus:ring-blue-500 outline-none text-zinc-900 dark:text-zinc-100"
                                        />
                                    </td>
                                ))}
                                <td className="px-2 py-3 text-right">
                                    <button
                                        onClick={() => deleteRow(rowIndex)}
                                        className="p-1.5 text-zinc-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md opacity-0 group-hover:opacity-100 transition-all"
                                        title="Delete row"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            {data.length === 0 && (
                <div className="text-center p-12 text-zinc-500">
                    No data. Add a row or column to start.
                </div>
            )}
        </div>
    );
}
