import {NextResponse} from "next/server";
import {getActionFeed} from "@/lib/api";

export async function GET() {
    try {
        const data = await getActionFeed();
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