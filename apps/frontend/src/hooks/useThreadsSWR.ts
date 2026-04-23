"use client";
import useSWR from "swr";
import { langgraph } from "@/lib/langgraph";

async function fetchThreads() {
  const client = langgraph();
  const list = await client.threads.search({ limit: 100 });
  return list.sort((a: any, b: any) =>
    new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime()
  );
}

export function useThreadsSWR() {
  const { data, isLoading, error, mutate } = useSWR("langgraph-threads", fetchThreads, {
    refreshInterval: 15_000,
    revalidateOnFocus: true,
    keepPreviousData: true,
  });
  return { threads: data ?? [], isLoading, error, mutate };
}
