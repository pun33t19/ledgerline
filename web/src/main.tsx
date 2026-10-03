import "./index.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { App } from "./App";
import { claimTokenFromUrl } from "./api/client";
import { initTheme } from "./lib/theme";

initTheme();
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});
const root = document.getElementById("root");
if (!root) throw new Error("index.html has no #root element");

// Exchange the link's token for a session cookie before anything asks the API.
claimTokenFromUrl()
  .catch(() => undefined) // a bad token simply leads to the "open the link" screen
  .finally(() => {
    createRoot(root).render(
      <StrictMode>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </QueryClientProvider>
      </StrictMode>,
    );
  });
