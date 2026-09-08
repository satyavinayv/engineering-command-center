"use client";

import {ExpandablePanel} from "./ExpandablePanel";
import type {CalendarEvent} from "@/lib/api";

function formatDate(iso: string | null) {
    if (!iso) return "Unknown time";
    return new Date(iso).toLocaleString();
}

export function CalendarPanel() {
    return (
        <section className="card">
            <h2>Calendar</h2>

            <ExpandablePanel<CalendarEvent>
                label="calendar events"
                fetchUrl="/api/bff/calendar"
                emptyLabel="No upcoming calendar events."
                renderItem={(event) => (
                    <div className="detail-item" key={event.source_uid}>
                        <div className="detail-item-title">{event.title}</div>

                        <div className="muted">
                            {formatDate(event.start_at)}
                        </div>

                        <div className="muted">
                            RSVP: {event.my_rsvp_status}
                        </div>

                        {event.location && (
                            <div className="muted">{event.location}</div>
                        )}

                        {event.calendar_link && (
                            <a
                                href={event.calendar_link}
                                target="_blank"
                                rel="noreferrer"
                            >
                                Open calendar
                            </a>
                        )}
                    </div>
                )}
            />
        </section>
    );
}