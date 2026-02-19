"use client";

import React, { useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";

const navItems = [
    { name: "Overview", href: "/" },
    { name: "Matches", href: "/matches" },
    { name: "Match Summary", href: "/summary" },
    { name: "Standings", href: "/standings" },
    { name: "Leaderboard", href: "/leaderboard" },
    { name: "Players", href: "/players" },
    { name: "Teams", href: "/teams" },
    { name: "Subs", href: "/substitutions" },
    { name: "Playoffs", href: "/playoffs" },
    { name: "Admin", href: "/admin", isAdmin: true },
];

export default function Navbar() {
    const [hoveredPath, setHoveredPath] = useState("/");

    return (
        <nav className="fixed top-0 left-0 w-full z-50 px-6 py-4">
            <div className="max-w-7xl mx-auto flex items-center justify-between glass px-8 py-3 rounded-2xl border border-white/5 shadow-2xl">
                {/* Logo */}
                <Link href="/" className="flex items-center gap-3 group">
                    <div className="w-10 h-10 bg-val-red rotate-45 flex items-center justify-center group-hover:rotate-90 transition-transform duration-500">
                        <div className="w-5 h-5 bg-white -rotate-45" />
                    </div>
                    <span className="font-display text-xl font-bold tracking-tighter uppercase leading-none">
                        S23 <span className="text-val-red">Portal</span>
                    </span>
                </Link>

                {/* Desktop Nav */}
                <div className="hidden md:flex items-center gap-1">
                    {navItems.map((item) => (
                        <Link
                            key={item.name}
                            href={item.href}
                            className={`relative px-4 py-2 text-sm font-medium tracking-wide uppercase transition-colors duration-300 ${item.isAdmin ? "text-val-red/80 hover:text-val-red" : "text-foreground/70 hover:text-foreground"
                                }`}
                            onMouseEnter={() => setHoveredPath(item.href)}
                        >
                            {item.name}
                            {hoveredPath === item.href && (
                                <motion.div
                                    layoutId="nav-hover"
                                    className="absolute inset-0 bg-white/5 rounded-lg -z-10"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                                />
                            )}
                        </Link>
                    ))}
                </div>

                {/* Mobile Toggle (Placeholder) */}
                <div className="md:hidden w-8 h-8 flex flex-col justify-center gap-1.5 cursor-pointer">
                    <div className="w-full h-0.5 bg-foreground" />
                    <div className="w-full h-0.5 bg-val-red" />
                    <div className="w-full h-0.5 bg-foreground" />
                </div>
            </div>
        </nav>
    );
}
