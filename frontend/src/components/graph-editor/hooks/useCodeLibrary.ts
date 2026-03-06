/**
 * TanStack Query hooks for the Code Library feature.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useToastMutation } from "@/hooks/useToastMutation";
import { api } from "@/lib/api";

export interface CodeBlockPortDef {
  name: string;
  type: string;
  description: string;
  required: boolean;
}

export interface CodeLibraryBlock {
  id: string;
  name: string;
  description: string | null;
  code: string;
  language: "python" | "javascript" | "bash";
  version: number;
  is_public: boolean;
  tags: string[];
  created_by: { id: string; username: string; display_name: string };
  is_favorited: boolean;
  input_ports: CodeBlockPortDef[] | null;
  output_ports: CodeBlockPortDef[] | null;
  created_at: string;
  updated_at: string;
}

export interface CodeLibraryPaletteEntry {
  type: string;
  name: string;
  category: string;
  subcategory: string | null;
  color: string;
  description: string;
  icon: string | null;
  input_ports: Array<{ name: string; type: string; description: string }>;
  output_ports: Array<{ name: string; type: string; description: string }>;
  properties: Array<{ name: string; type: string; default_value?: unknown; ui_type?: string }>;
  is_library_block: true;
  library_block_id: string;
  library_block_version: number;
  is_favorited: boolean;
  creator_name: string;
}

export interface CodeLibraryUserCategory {
  id: string;
  name: string;
  parent_id: string | null;
  sort_order: number;
}

interface PaginatedResponse<T> {
  data: T[];
  meta: { total: number; page: number; per_page: number; total_pages: number };
}

/** Fetch library blocks formatted for the NodePalette */
export function useCodeLibraryPalette() {
  return useQuery({
    queryKey: ["code-library", "palette"],
    queryFn: () => api.get<CodeLibraryPaletteEntry[]>("/code-library/palette"),
    staleTime: 30_000,
  });
}

/** Fetch all blocks with pagination */
export function useCodeLibraryBlocks(params?: {
  search?: string;
  language?: string;
  page?: number;
  per_page?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.search) searchParams.set("search", params.search);
  if (params?.language) searchParams.set("language", params.language);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.per_page) searchParams.set("per_page", String(params.per_page));

  const qs = searchParams.toString();
  return useQuery({
    queryKey: ["code-library", "blocks", params],
    queryFn: () =>
      api.get<PaginatedResponse<CodeLibraryBlock>>(
        `/code-library${qs ? `?${qs}` : ""}`
      ),
  });
}

/** Fetch a single block */
export function useCodeLibraryBlock(blockId: string | undefined) {
  return useQuery({
    queryKey: ["code-library", "block", blockId],
    queryFn: () => api.get<CodeLibraryBlock>(`/code-library/${blockId}`),
    enabled: !!blockId,
  });
}

/** Fetch user's custom categories */
export function useCodeLibraryCategories() {
  return useQuery({
    queryKey: ["code-library", "categories"],
    queryFn: () => api.get<CodeLibraryUserCategory[]>("/code-library/categories"),
  });
}

/** Create a new block */
export function useCreateBlock() {
  const queryClient = useQueryClient();
  return useToastMutation({
    loadingMessage: "Saving code block...",
    successMessage: "Code block saved.",
    mutationFn: (data: {
      name: string;
      code?: string;
      language?: string;
      description?: string;
      is_public?: boolean;
      tags?: string[];
      input_ports?: Array<{ name: string; type: string; description: string; required: boolean }>;
      output_ports?: Array<{ name: string; type: string; description: string; required: boolean }>;
    }) => api.post<CodeLibraryBlock>("/code-library", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["code-library"] });
    },
  });
}

/** Update a block */
export function useUpdateBlock() {
  const queryClient = useQueryClient();
  return useToastMutation({
    loadingMessage: "Saving code block...",
    successMessage: "Code block saved.",
    mutationFn: ({
      blockId,
      ...data
    }: {
      blockId: string;
      name?: string;
      code?: string;
      language?: string;
      description?: string;
      is_public?: boolean;
      tags?: string[];
      input_ports?: Array<{ name: string; type: string; description: string; required: boolean }>;
      output_ports?: Array<{ name: string; type: string; description: string; required: boolean }>;
    }) => api.patch<CodeLibraryBlock>(`/code-library/${blockId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["code-library"] });
    },
  });
}

/** Delete a block */
export function useDeleteBlock() {
  const queryClient = useQueryClient();
  return useToastMutation({
    loadingMessage: "Deleting code block...",
    successMessage: "Code block deleted.",
    mutationFn: (blockId: string) => api.delete(`/code-library/${blockId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["code-library"] });
    },
  });
}

/** Toggle favorite on a block */
export function useToggleFavorite() {
  const queryClient = useQueryClient();
  return useToastMutation({
    loadingMessage: false,
    successMessage: false,
    mutationFn: (blockId: string) =>
      api.post<{ is_favorited: boolean }>(`/code-library/${blockId}/favorite`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["code-library"] });
    },
  });
}

/** Create a category */
export function useCreateCategory() {
  const queryClient = useQueryClient();
  return useToastMutation({
    loadingMessage: false,
    successMessage: "Category created.",
    mutationFn: (data: { name: string; parent_id?: string; sort_order?: number }) =>
      api.post<CodeLibraryUserCategory>("/code-library/categories", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["code-library", "categories"] });
      queryClient.invalidateQueries({ queryKey: ["code-library", "palette"] });
    },
  });
}

/** Update a category */
export function useUpdateCategory() {
  const queryClient = useQueryClient();
  return useToastMutation({
    loadingMessage: false,
    successMessage: "Category updated.",
    mutationFn: ({
      categoryId,
      ...data
    }: {
      categoryId: string;
      name?: string;
      parent_id?: string | null;
      sort_order?: number;
    }) => api.patch<CodeLibraryUserCategory>(`/code-library/categories/${categoryId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["code-library", "categories"] });
      queryClient.invalidateQueries({ queryKey: ["code-library", "palette"] });
    },
  });
}

/** Delete a category */
export function useDeleteCategory() {
  const queryClient = useQueryClient();
  return useToastMutation({
    loadingMessage: false,
    successMessage: "Category deleted.",
    mutationFn: (categoryId: string) => api.delete(`/code-library/categories/${categoryId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["code-library", "categories"] });
      queryClient.invalidateQueries({ queryKey: ["code-library", "palette"] });
    },
  });
}

/** Assign a block to a user category */
export function useAssignBlockCategory() {
  const queryClient = useQueryClient();
  return useToastMutation({
    loadingMessage: false,
    successMessage: false,
    mutationFn: ({
      blockId,
      categoryId,
    }: {
      blockId: string;
      categoryId: string | null;
    }) =>
      api.put(
        `/code-library/${blockId}/assign-category${categoryId ? `?category_id=${categoryId}` : ""}`
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["code-library", "palette"] });
    },
  });
}
