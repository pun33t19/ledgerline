import { useEffect, useReducer } from "react";
import { applyEvent, initialRun, type RunView } from "../lib/runState";
import type { RunEvent } from "./types";

/** Streams a run's events over a WebSocket and folds them into a RunView. */
export function useRunEvents(runId: string | undefined): RunView {
  const [view, dispatch] = useReducer(
    (state: RunView, action: RunEvent | { type: "reset" } | { type: "socket_error" }) => {
      if (action.type === "reset") return initialRun();
      if (action.type === "socket_error")
        return state.status === "finished"
          ? state
          : { ...state, status: "failed" as const, error: "Lost the connection to `ledgerline ui`." };
      return applyEvent(state, action);
    },
    undefined,
    initialRun,
  );

  useEffect(() => {
    if (!runId) return;
    dispatch({ type: "reset" });
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${scheme}://${window.location.host}/api/runs/${runId}/events`);
    socket.onmessage = (message) => dispatch(JSON.parse(String(message.data)) as RunEvent);
    socket.onerror = () => dispatch({ type: "socket_error" });
    return () => socket.close();
  }, [runId]);

  return view;
}
