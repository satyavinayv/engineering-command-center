import {NextRequest, NextResponse} from "next/server";
import {
    getGmailActionRequired,
    getGmailUnread,
} from "@/lib/api";

export async function GET(req: NextRequest) {
    const kind =
        req.nextUrl.searchParams.get("kind") === "action-required"
            ? "action-required"
            : "unread";

    try {
        const data =
            kind === "action-required"
                ? await getGmailActionRequired()
                : await getGmailUnread();

        return NextResponse.json(data);
    } catch (err) {
        return NextResponse.json(
            {
                error: err instanceof Error ? err.message : "Unknown error",
            },
            {status: 502}
        );
    }
}