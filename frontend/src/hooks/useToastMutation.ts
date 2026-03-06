import { useMutation, type UseMutationOptions } from "@tanstack/react-query";
import { useToast } from "@/stores/toastStore";
import { useRef } from "react";

type ToastMutationOptions<
  TData = unknown,
  TError = { detail?: string; message?: string },
  TVariables = void,
  TContext = unknown,
> = UseMutationOptions<TData, TError, TVariables, TContext> & {
  /** Message shown if request takes >1s. Pass false to disable. */
  loadingMessage?: string | false;
  /** Message on success. Pass false to disable. */
  successMessage?: string | ((data: TData) => string) | false;
  /** Message on error. Pass false to disable. */
  errorMessage?: string | ((error: TError) => string) | false;
};

export function useToastMutation<
  TData = unknown,
  TError = { detail?: string; message?: string },
  TVariables = void,
  TContext = unknown,
>(options: ToastMutationOptions<TData, TError, TVariables, TContext>) {
  const { toast, dismiss } = useToast();
  const infoToastId = useRef<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const {
    loadingMessage = "Working...",
    successMessage = "Done.",
    errorMessage,
    onMutate,
    onSuccess,
    onError,
    onSettled,
    ...mutationOptions
  } = options;

  return useMutation<TData, TError, TVariables, TContext>({
    ...mutationOptions,
    onMutate: async (variables) => {
      if (loadingMessage !== false) {
        timerRef.current = setTimeout(() => {
          infoToastId.current = toast("info", loadingMessage, 0);
        }, 1000);
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return (onMutate as any)?.(variables) as TContext;
    },
    onSuccess: (data, variables, context) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (infoToastId.current) dismiss(infoToastId.current);
      timerRef.current = null;
      infoToastId.current = null;

      if (successMessage !== false) {
        const msg =
          typeof successMessage === "function" ? successMessage(data) : successMessage;
        toast("success", msg);
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (onSuccess as any)?.(data, variables, context);
    },
    onError: (error, variables, context) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (infoToastId.current) dismiss(infoToastId.current);
      timerRef.current = null;
      infoToastId.current = null;

      if (errorMessage !== false) {
        const msg =
          typeof errorMessage === "function"
            ? errorMessage(error)
            : errorMessage ||
              (error as { detail?: string })?.detail ||
              (error as { message?: string })?.message ||
              "Something went wrong.";
        toast("error", msg);
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (onError as any)?.(error, variables, context);
    },
    onSettled,
  });
}
