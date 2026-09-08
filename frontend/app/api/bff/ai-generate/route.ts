import {NextResponse} from "next/server";
import {regenerateDailyBriefing} from "@/lib/api";

export async function POST() {
    try {
        const data = await regenerateDailyBriefing();
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