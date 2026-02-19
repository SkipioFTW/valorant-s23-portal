'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface Player {
    id: number;
    name: string;
    riot_id: string;
}

interface Props {
    players: Player[];
    onSelect: (id: number) => void;
    currentId: number | null;
}

export default function PlayerSearch({ players, onSelect, currentId }: Props) {
    const [query, setQuery] = useState('');
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    const filteredPlayers = query.trim() === ''
        ? players.slice(0, 10)
        : players.filter(p =>
            p.name.toLowerCase().includes(query.toLowerCase()) ||
            p.riot_id.toLowerCase().includes(query.toLowerCase())
        ).slice(0, 10);

    const currentPlayer = players.find(p => p.id === currentId);

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    return (
        <div className="relative w-full max-w-md" ref={containerRef}>
            <div
                className="glass rounded-lg border border-white/10 flex items-center px-4 py-3 cursor-text focus-within:border-val-red transition-all"
                onClick={() => setIsOpen(true)}
            >
                <div className="flex-1">
                    <input
                        type="text"
                        placeholder="Search Player Name or Riot ID..."
                        value={query || (isOpen ? '' : (currentPlayer?.name || ''))}
                        onChange={(e) => {
                            setQuery(e.target.value);
                            setIsOpen(true);
                        }}
                        onFocus={() => setIsOpen(true)}
                        className="bg-transparent border-none outline-none w-full text-foreground font-bold"
                    />
                </div>
                <div className="text-foreground/40">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                </div>
            </div>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 10 }}
                        className="absolute z-50 left-0 right-0 mt-2 glass rounded-xl border border-white/10 shadow-2xl overflow-hidden max-h-[300px] overflow-y-auto"
                    >
                        {filteredPlayers.length > 0 ? (
                            filteredPlayers.map(p => (
                                <button
                                    key={p.id}
                                    onClick={() => {
                                        onSelect(p.id);
                                        setQuery('');
                                        setIsOpen(false);
                                    }}
                                    className={`w-full text-left px-4 py-3 flex items-center justify-between hover:bg-val-red/10 transition-colors ${p.id === currentId ? 'bg-val-red/5 text-val-red' : ''}`}
                                >
                                    <div>
                                        <div className="font-bold">{p.name}</div>
                                        <div className="text-xs text-foreground/40">{p.riot_id}</div>
                                    </div>
                                    {p.id === currentId && (
                                        <div className="w-2 h-2 rounded-full bg-val-red" />
                                    )}
                                </button>
                            ))
                        ) : (
                            <div className="px-4 py-8 text-center text-foreground/40 italic">
                                No players found matching "{query}"
                            </div>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
