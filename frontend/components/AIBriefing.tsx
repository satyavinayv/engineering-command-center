"use client";

import {useState} from "react";
import type {DailyBriefing} from "@/lib/api";

function formatTime(iso: string | null): string {
    if (!iso) return "never";

    return new Date(iso).toLocaleString();
}

export function AIBriefing({
                               initial,
                               aiEnabled,
                           }: {
    initial: DailyBriefing;
    aiEnabled: boolean;
}) {
    const [briefing, setBriefing] =
        useState<DailyBriefing>(initial);

    const [regenerating, setRegenerating] =
        useState(false);

    const [error, setError] =
        useState<string | null>(null);

    async function handleRegenerate() {
        setRegenerating(true);
        setError(null);

        try {
            const res = await fetch(
                "/api/bff/ai-regenerate",
                {
                    method: "POST",
                }
            );

            if (!res.ok) {
                throw new Error(
                    `Request failed (${res.status})`
                );
            }

            const data: DailyBriefing = await res.json();

            setBriefing(data);
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Failed to regenerate"
            );
        } finally {
            setRegenerating(false);
        }


    }

    if (!aiEnabled) {
        return (
            <section className="card ai-card">
                <h2>AI Daily Briefing</h2>

                <p className="muted">
                    AI is disabled. Action Required below is
                    fully deterministic and works without AI.
                </p>
            </section>
        );


    }

    return (
        <section className="card ai-card">
            <div className="card-header-row">
                <h2>AI Daily Briefing</h2>

                <button
                    type="button"
                    className="expand-btn"
                    onClick={handleRegenerate}
                    disabled={regenerating}
                >
                    {regenerating
                        ? "Regenerating..."
                        : "Regenerate"}
                </button>
            </div>

            {error && (
                <p className="error-text">
                    Could not regenerate: {error}
                </p>
            )}

            {!briefing.available && !error && (
                <p className="muted">
                    No briefing generated yet. The background
                    scheduler will produce one shortly, or click
                    Regenerate to trigger it now.
                </p>
            )}

            {briefing.available && (
                <>
                    <p className="ai-content">
                        {briefing.content}
                    </p>

                    <p className="muted ai-meta">
                        {briefing.cached
                            ? "Cached"
                            : "Freshly generated"}{" "}
                        · {briefing.generated_by} ·{" "}
                        {formatTime(briefing.created_at)}
                    </p>
                </>
            )}
        </section>


    );
}