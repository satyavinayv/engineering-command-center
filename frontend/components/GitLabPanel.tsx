"use client";

import {useState} from "react";
import {ExpandablePanel} from "./ExpandablePanel";
import type {GitLabMergeRequest} from "@/lib/api";

export function GitLabPanel({
                                reviewWaitingCount,
                            }: {
    reviewWaitingCount: number;
}) {
    const [kind, setKind] = useState<"to-review" | "mine">("to-review");

    return (
        <section className="card">
            <div className="card-header-row">
                <h2>GitLab</h2>

                <div className="panel-tabs">
                    <button
                        type="button"
                        className={kind === "to-review" ? "active" : ""}
                        onClick={() => setKind("to-review")}
                    >
                        Reviews ({reviewWaitingCount})
                    </button>

                    <button
                        type="button"
                        className={kind === "mine" ? "active" : ""}
                        onClick={() => setKind("mine")}
                    >
                        My MRs
                    </button>
                </div>
            </div>

            <ExpandablePanel<GitLabMergeRequest>
                label="merge requests"
                fetchUrl={`/api/bff/gitlab?kind=${kind}`}
                emptyLabel="No merge requests."
                renderItem={(mr) => (
                    <div className="detail-item" key={`${mr.source_id}-${mr.iid}`}>
                        <div className="detail-item-title">
                            !{mr.iid} — {mr.title}
                        </div>

                        <div className="muted">
                            {mr.computed_state}
                            {mr.pipeline_status
                                ? ` · Pipeline: ${mr.pipeline_status}`
                                : ""}
                        </div>

                        <div className="muted">
                            Author: {mr.author}
                        </div>

                        <a
                            href={mr.web_url}
                            target="_blank"
                            rel="noreferrer"
                        >
                            Open merge request
                        </a>
                    </div>
                )}
            />
        </section>
    );
}