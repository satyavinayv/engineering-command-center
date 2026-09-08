"use client";

import {useState} from "react";
import {PriorityBadge} from "./Badges";
import type {ActionItem} from "@/lib/api";

function formatTime(value: string | null): string {
    if (!value) return "";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return value;
    }

    const pad = (n: number) => String(n).padStart(2, "0");

    return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}, ${pad(
        date.getHours()
    )}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

const SOURCE_LABELS: Record<string, string> = {
    gitlab: "GitLab",
    jira: "Jira",
    calendar: "Calendar",
    gmail: "Gmail",
    tests: "Tests",
};

function ActionRow({
                       item,
                   }: {
    item: ActionItem;
}) {
    const body = (
        <>
            <div className="action-row-top">
                <PriorityBadge priority={item.priority}/>

                <span className="action-source">
      {SOURCE_LABELS[item.source] ?? item.source}
    </span>

                {item.timestamp && (
                    <span className="muted action-time">
        {formatTime(item.timestamp)}
      </span>
                )}
            </div>

            <div className="action-title">
                {item.title}
            </div>

            <div className="muted action-desc">
                {item.description}
            </div>
        </>


    );

    if (item.url) {
        return (
            <a className="action-row" href={item.url} target="_blank" rel="noreferrer">
                {body}
            </a>
        );
    }

    return (
        <div className="action-row">
            {body}
        </div>
    );
}

export function ActionRequired({
                                   count,
                                   items,
                               }: {
    count: number;
    items: ActionItem[];
}) {
    const [feed, setFeed] =
        useState<ActionItem[] | null>(null);

    const [loadingFeed, setLoadingFeed] =
        useState(false);

    const [feedError, setFeedError] =
        useState<string | null>(null);

    const [showFeed, setShowFeed] =
        useState(false);

    async function handleShowFullFeed() {
        if (showFeed) {
            setShowFeed(false);
            return;
        }

        setShowFeed(true);

        if (feed !== null) {
            return;
        }

        setLoadingFeed(true);
        setFeedError(null);

        try {
            const res = await fetch(
                "/api/bff/action-feed",
                {
                    cache: "no-store",
                }
            );

            if (!res.ok) {
                throw new Error(
                    `Request failed (${res.status})`
                );
            }

            const data = await res.json();

            setFeed(
                Array.isArray(data) ? data : []
            );
        } catch (err) {
            setFeedError(
                err instanceof Error
                    ? err.message
                    : "Failed to load"
            );
        } finally {
            setLoadingFeed(false);
        }


    }

    const displayed =
        showFeed && feed ? feed : items;

    return (
        <section className="card action-required-card">
            <div className="card-header-row">
                <h2>
                    Action Required ({count})
                </h2>

                {count > items.length &&
                    !showFeed && (
                        <span className="muted">
          Showing top {items.length} of {count}
        </span>
                    )}
            </div>

            {count === 0 && (
                <p className="muted">
                    Nothing needs your attention right now.
                </p>
            )}

            {count > 0 && (
                <div className="action-list">
                    {displayed.map((item) => (
                        <ActionRow
                            key={item.key}
                            item={item}
                        />
                    ))}
                </div>
            )}

            {count > items.length && (
                <button
                    type="button"
                    className="expand-btn"
                    onClick={handleShowFullFeed}
                >
                    {showFeed
                        ? "Show top items only"
                        : "Show full activity feed (incl. P3)"}
                </button>
            )}

            {loadingFeed && (
                <p className="muted">
                    Loading full feed...
                </p>
            )}

            {feedError && (
                <p className="error-text">
                    Could not load full feed: {feedError}
                </p>
            )}
        </section>


    );
}