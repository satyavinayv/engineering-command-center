import {StatusDot} from "./Badges";

export function Header({
                           status,
                           connected,
                       }: {
    status: "ok" | "degraded" | "disconnected";
    connected: boolean;
}) {
    const today = new Intl.DateTimeFormat("en-IN", {
        weekday: "long",
        day: "numeric",
        month: "short",
        timeZone: "Asia/Kolkata",
    }).format(new Date());

    const statusLabel =
        status === "ok"
            ? "All systems normal"
            : status === "degraded"
                ? "Degraded"
                : "Disconnected";

    return (
        <header className="header">
            <div>
                <h1>Engineering Command Center</h1>
                <span className="date">{today}</span>
            </div>

            <div className={`status-pill status-${status}`}>
                <StatusDot ok={connected}/>
                {statusLabel}
            </div>
        </header>


    );
}