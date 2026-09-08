export function PriorityBadge({
                                  priority,
                              }: {
    priority: string;
}) {
    return (
        <span
            className={`priority-badge priority-${priority.toLowerCase()}`}
        >
      {priority}
    </span>
    );
}

export function StatusDot({
                              ok,
                          }: {
    ok: boolean;
}) {
    return (
        <span
            className={`dot ${ok ? "connected" : "disconnected"}`}
            aria-hidden="true"
        />
    );
}
