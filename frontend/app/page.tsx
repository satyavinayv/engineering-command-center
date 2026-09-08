import {Header} from "@/components/Header";
import {SystemHealth} from "@/components/SystemHealth";
import {AIBriefing} from "@/components/AIBriefing";
import {ActionRequired} from "@/components/ActionRequired";
import {CalendarPanel} from "@/components/CalendarPanel";
import {GmailPanel} from "@/components/GmailPanel";
import {JiraPanel} from "@/components/JiraPanel";
import {GitLabPanel} from "@/components/GitLabPanel";
import {TestAutomationPanel} from "@/components/TestAutomationPanel";

import {
    BackendUnavailableError,
    getDashboardSummary,
    getDailyBriefing,
    getHealth,
} from "@/lib/api";

export default async function Home() {
    const [summaryResult, healthResult, briefingResult] =
        await Promise.allSettled([
            getDashboardSummary(),
            getHealth(),
            getDailyBriefing(),
        ]);

    const summary =
        summaryResult.status === "fulfilled"
            ? summaryResult.value
            : null;

    const health =
        healthResult.status === "fulfilled"
            ? healthResult.value
            : null;

    const briefing =
        briefingResult.status === "fulfilled"
            ? briefingResult.value
            : {
                available: false,
                content: null,
                generated_by: null,
                created_at: null,
                cached: false,
            };

    const connected =
        summary !== null || health !== null;

    const status =
        !connected
            ? "disconnected"
            : summary?.health.status === "degraded" ||
            health?.status === "degraded"
                ? "degraded"
                : "ok";

    return (
        <main className="dashboard">
            <Header
                status={status}
                connected={connected}
            />

            <div className="dashboard-content">
                <SystemHealth
                    integrations={health?.integrations ?? null}
                    aiEnabled={health?.ai_enabled ?? summary?.ai.enabled ?? false}
                    error={
                        !connected
                            ? "Backend unavailable"
                            : null
                    }
                />

                {summary && (
                    <>
                        <AIBriefing
                            initial={briefing}
                            aiEnabled={summary.ai.enabled}
                        />

                        <ActionRequired
                            count={summary.action_required.count}
                            items={summary.action_required.top_items}
                        />

                        <div className="dashboard-grid">
                            <CalendarPanel/>

                            <GmailPanel
                                unreadCount={summary.gmail.unread_count}
                                actionRequiredCount={
                                    summary.gmail.action_required_count
                                }
                            />

                            <JiraPanel/>

                            <GitLabPanel
                                reviewWaitingCount={
                                    summary.gitlab.review_waiting_count
                                }
                            />

                            <TestAutomationPanel
                                failCount={summary.tests.fail_count}
                                passCount={summary.tests.pass_count}
                            />
                        </div>
                    </>
                )}

                {!summary && (
                    <section className="card error-card">
                        <h2>Dashboard unavailable</h2>
                        <p>
                            The frontend could not retrieve the dashboard
                            summary from the backend.
                        </p>
                    </section>
                )}
            </div>
        </main>
    );
}