import {NextRequest, NextResponse} from "next/server";
import {
    getMergeRequestsToReview,
    getMyOpenMergeRequests,
} from "@/lib/api";

export async function GET(req: NextRequest) {
    const kind =
        req.nextUrl.searchParams.get("kind") === "mine"
            ? "mine"
            : "to-review";

    try {
        const data =
            kind === "mine"
                ? await getMyOpenMergeRequests()
                : await getMergeRequestsToReview();

        return NextResponse.json(data);
    } catch (err) {
        return NextResponse.json(
            {
                error:
                    err instanceof Error
                        ? err.message
                        : "unknown error",
            },
            {status: 502}
        );
    }
}