"use client";

import {useState} from "react";
import {ExpandablePanel} from "./ExpandablePanel";
import type {EmailMessage} from "@/lib/api";

export function GmailPanel({
                               unreadCount,
                               actionRequiredCount,
                           }: {
    unreadCount: number;
    actionRequiredCount: number;
}) {
    const [kind, setKind] = useState<"unread" | "action-required">("unread");

    return (
        <section className="card">
            <div className="card-header-row">
                <h2>Gmail</h2>

                <div className="panel-tabs">
                    <button
                        type="button"
                        className={kind === "unread" ? "active" : ""}
                        onClick={() => setKind("unread")}
                    >
                        Unread ({unreadCount})
                    </button>

                    <button
                        type="button"
                        className={kind === "action-required" ? "active" : ""}
                        onClick={() => setKind("action-required")}
                    >
                        Action Required ({actionRequiredCount})
                    </button>
                </div>
            </div>

            <ExpandablePanel<EmailMessage>
                label="messages"
                fetchUrl={`/api/bff/gmail?kind=${kind}`}
                emptyLabel="No messages."
                renderItem={(message) => (
                    <div className="detail-item" key={message.message_id}>
                        <div className="detail-item-title">
                            {message.subject || "(No subject)"}
                        </div>

                        <div className="muted">
                            From: {message.from_addr}
                        </div>

                        <div className="muted">
                            {message.received_at
                                ? new Date(message.received_at).toLocaleString()
                                : ""}
                        </div>

                        {message.action_required && (
                            <span className="priority-badge priority-p1">
                Action Required
              </span>
                        )}
                    </div>
                )}
            />
        </section>
    );
}