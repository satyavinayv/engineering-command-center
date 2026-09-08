import {NextResponse} from "next/server";
import {getTestExecutions} from "@/lib/api";

export async function GET() {
    try {
        const data = await getTestExecutions();
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