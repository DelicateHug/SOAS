/**
 * VSCode webview API wrapper.
 * Provides typed access to acquireVsCodeApi() and message handling.
 */

interface VsCodeApi {
  postMessage(message: unknown): void;
  getState(): unknown;
  setState(state: unknown): void;
}

// acquireVsCodeApi can only be called once
let vscodeApi: VsCodeApi | undefined;

export function getVsCodeApi(): VsCodeApi {
  if (!vscodeApi) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    vscodeApi = (window as any).acquireVsCodeApi();
  }
  return vscodeApi!;
}
