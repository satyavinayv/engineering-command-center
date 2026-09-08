import {NextResponse} from "next/server";
import {getJiraIssues} from "@/lib/api";

export async function GET() {
    try {
        const data = await getJiraIssues();
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