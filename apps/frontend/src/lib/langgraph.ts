"use client";
import { Client } from "@langchain/langgraph-sdk";
import { LANGGRAPH_API_URL } from "./env";

let _client: Client | null = null;
export function langgraph(): Client {
  if (_client) return _client;
  if (!LANGGRAPH_API_URL) throw new Error("Missing NEXT_PUBLIC_LANGGRAPH_API_URL");
  _client = new Client({ apiUrl: LANGGRAPH_API_URL });
  return _client;
}
