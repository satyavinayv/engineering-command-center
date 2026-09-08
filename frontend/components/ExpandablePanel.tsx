"use client";

import { useState } from "react";

export function ExpandablePanel<T>({
  label,
  fetchUrl,
  renderItem,
  emptyLabel = "Nothing to show.",
}: {
  label: string;
  fetchUrl: string;
  renderItem: (item: T, index: number) => React.ReactNode;
  emptyLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<T[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleToggle() {
    if (open) {
      setOpen(false);
      return;
    }

    setOpen(true);

    if (items !== null) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(fetchUrl, {
        cache: "no-store",
      });

      if (!res.ok) {
        throw new Error(`Request failed (${res.status})`);
      }

      const data = await res.json();

      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="expandable">
      <button
        type="button"
        className="expand-btn"
        onClick={handleToggle}
      >
        {open ? `Hide ${label}` : `Show ${label}`}
      </button>

      {open && (
        <div className="expandable-body">
          {loading && (
            <p className="muted">Loading...</p>
          )}

          {error && (
            <p className="error-text">
              Could not load: {error}
            </p>
          )}

          {!loading &&
            !error &&
            items &&
            items.length === 0 && (
              <p className="muted">
                {emptyLabel}
              </p>
            )}

          {!loading &&
            !error &&
            items &&
            items.length > 0 && (
              <div className="detail-list">
                {items.map((item, i) =>
                  renderItem(item, i)
                )}
              </div>
            )}
        </div>
      )}
    </div>
  );
}
