"use client";
import { Client } from "@langchain/langgraph-sdk";

/**
 * LangGraph client configuration for MPFE.
 *
 * The agent ships as a single graph called "syllabus" (see
 * apps/agent/langgraph.json). Local dev uses `langgraph dev` which listens on
 * http://localhost:2024 by default. Set `NEXT_PUBLIC_LANGGRAPH_URL` in
 * .env.local to point at a deployed instance.
 */

const DEFAULT_AGENT_URL = "http://localhost:2024";
const DEFAULT_ASSISTANT = "syllabus";

function nonEmpty(v: string | undefined | null): string | undefined {
  if (typeof v !== "string") return undefined;
  const t = v.trim();
  return t.length > 0 ? t : undefined;
}

export const LANGGRAPH_API_URL =
  nonEmpty(process.env.NEXT_PUBLIC_LANGGRAPH_URL) ?? DEFAULT_AGENT_URL;

export const CLASSIC_ASSISTANT_ID =
  nonEmpty(process.env.NEXT_PUBLIC_ASSISTANT_ID) ?? DEFAULT_ASSISTANT;

// Back-compat: MPFE only exposes a single supervisor graph for now. Variant
// selectors still pick different assistant ids for future deployments but
// default everything to the one that exists.
export const DEEP_ASSISTANT_ID =
  nonEmpty(process.env.NEXT_PUBLIC_DEEP_ASSISTANT_ID) ?? CLASSIC_ASSISTANT_ID;

export const V2_ASSISTANT_ID =
  nonEmpty(process.env.NEXT_PUBLIC_V2_ASSISTANT_ID) ?? CLASSIC_ASSISTANT_ID;

export const ASSISTANT_ID = CLASSIC_ASSISTANT_ID;

export type AgentVariant = "classic" | "deep" | "v2";

export function assistantIdFor(variant: AgentVariant | undefined | null): string {
  if (variant === "deep") return DEEP_ASSISTANT_ID;
  if (variant === "v2") return V2_ASSISTANT_ID;
  return CLASSIC_ASSISTANT_ID;
}

/** Optional API key for an auth-enabled LangGraph deployment. */
export function langgraphHeaders(): Record<string, string> | undefined {
  const key = nonEmpty(process.env.NEXT_PUBLIC_LANGGRAPH_API_KEY);
  return key ? { "x-api-key": key } : undefined;
}

let _client: Client | null = null;
export function getLangGraphClient(): Client {
  if (_client) return _client;
  _client = new Client({
    apiUrl: LANGGRAPH_API_URL,
    defaultHeaders: langgraphHeaders(),
  });
  return _client;
}
