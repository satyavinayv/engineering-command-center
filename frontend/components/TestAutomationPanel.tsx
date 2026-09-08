"use client";

import {ExpandablePanel} from "./ExpandablePanel";
import type {TestExecution} from "@/lib/api";

export function TestAutomationPanel({
                                        failCount,
                                        passCount,
                                    }: {
    failCount: number;
    passCount: number;
}) {
    return (
        <section className="card">
            <div className="card-header-row">
                <h2>Test Automation</h2>

                <div className="metric-summary">
          <span className="test-fail">
            Failed: {failCount}
          </span>

                    <span className="test-pass">
            Passed: {passCount}
          </span>
                </div>
            </div>

            <ExpandablePanel<TestExecution>
                label="test executions"
                fetchUrl="/api/bff/tests"
                emptyLabel="No test executions."
                renderItem={(test, index) => (
                    <div className="detail-item" key={`${test.test_case_key}-${index}`}>
                        <div className="detail-item-title">
                            {test.test_case_key}
                        </div>

                        <div className="muted">
                            {test.status || "Unknown"} · {test.environment}
                        </div>

                        {test.jira_summary && (
                            <div className="muted">
                                {test.jira_summary}
                            </div>
                        )}

                        {test.jira_url && (
                            <a
                                href={test.jira_url}
                                target="_blank"
                                rel="noreferrer"
                            >
                                Open Jira
                            </a>
                        )}
                    </div>
                )}
            />
        </section>
    );
}