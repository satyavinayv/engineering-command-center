import {NextResponse} from "next/server";
import {getCalendarEvents} from "@/lib/api";

export async function GET() {
    try {
        const data = await getCalendarEvents();
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