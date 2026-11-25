import { useEffect, useState, useCallback } from "react";
import { getHealth, getModels } from "../services/api";
import type { ModelInfo } from "../types/api";
export const CONNECTION_RETRY_MS = 15_000;
export function useService() {
  const [revision, setRevision] = useState(0);
  const [status, setStatus] = useState<
    "loading" | "online" | "empty" | "offline" | "error"
  >("loading");
  const [models, setModels] = useState<ModelInfo[]>([]);
  const reload = useCallback(() => {
    setStatus("loading");
    setRevision((n) => n + 1);
  }, []);
  useEffect(() => {
    const ctrl = new AbortController();
    async function load() {
      const [health, list] = await Promise.allSettled([
        getHealth(ctrl.signal),
        getModels(ctrl.signal),
      ]);
      if (ctrl.signal.aborted) return;
      setModels(list.status === "fulfilled" ? list.value : []);
      setStatus(
        list.status === "fulfilled"
          ? list.value.length
            ? "online"
            : "empty"
          : health.status === "fulfilled"
            ? "error"
            : "offline",
      );
    }
    void load();
    return () => ctrl.abort();
  }, [revision]);
  useEffect(() => {
    if (status === "online" || status === "loading") return;
    const timer = window.setTimeout(reload, CONNECTION_RETRY_MS);
    return () => window.clearTimeout(timer);
  }, [reload, status]);
  return { status, models, reload };
}
export type Service = ReturnType<typeof useService>;
