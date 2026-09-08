"use client";

import {ExpandablePanel} from "./ExpandablePanel";
import type {JiraIssue} from "@/lib/api";

export function JiraPanel() {
    return (
        <section className="card">
            <h2>Jira</h2>

            <ExpandablePanel<JiraIssue>
                label="Jira issues"
                fetchUrl="/api/bff/jira"
                emptyLabel="No Jira issues found."
                renderItem={(issue) => (
                    <div className="detail-item" key={issue.key}>
                        <div className="detail-item-title">
                            {issue.key} — {issue.summary}
                        </div>

                        <div className="muted">
                            {issue.status} · {issue.priority}
                        </div>

                        {issue.assignee && (
                            <div className="muted">
                                Assignee: {issue.assignee}
                            </div>
                        )}

                        <a
                            href={issue.url}
                            target="_blank"
                            rel="noreferrer"
                        >
                            Open Jira
                        </a>
                    </div>
                )}
            />
        </section>
    );
}