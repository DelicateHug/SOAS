/**
 * React Query client for webview panels.
 */

import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false, // Webviews don't have traditional window focus
    },
  },
});
