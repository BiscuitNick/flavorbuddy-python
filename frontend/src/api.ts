export type User = { id: number; email: string };
export type Content = {
  private_cover?: string | null;
  title: string;
  description: string;
  author: string;
  total_time: number | null;
  yields: string;
  source_url: string | null;
  image: string;
  ingredients: string[];
  instructions: string[];
  notes?: string;
  favorite?: boolean;
};
export type Recipe = Content & {
  provenance?: {
    license?: string;
    license_url?: string;
    source_url?: string;
    revision?: string;
  };
  id: number;
  public_id: string;
  state: "draft" | "finalized";
  visibility: "private" | "public";
  inspired_by_recipe_id: string | null;
  version: number;
  notes: string;
  favorite: boolean;
};
export type Draft = {
  id: number;
  state: string;
  content: Content;
  error_code: string;
  recipe_id: number | null;
};
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public fields: Record<string, string[]> = {},
    public code = "",
  ) {
    super(message);
  }
}
let csrf = "";
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch("/api/v1/" + path, {
      method,
      credentials: "same-origin",
      headers: {
        ...(body instanceof FormData
          ? {}
          : { "Content-Type": "application/json" }),
        ...(csrf ? { "X-CSRFToken": csrf } : {}),
      },
      ...(body !== undefined
        ? { body: body instanceof FormData ? body : JSON.stringify(body) }
        : {}),
    });
  } catch {
    throw new ApiError(
      0,
      "Could not connect. Your work is still here. Check your connection and try again.",
    );
  }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => ({
    error: {
      message: "The server could not complete this request. Please try again.",
    },
  }));
  if (
    !response.ok &&
    response.status === 403 &&
    data.error?.code === "not_authenticated"
  ) {
    window.dispatchEvent(new Event("fb:session-expired"));
  }
  if (!response.ok)
    throw new ApiError(
      response.status,
      data.error?.message || "Please try again.",
      data.error?.fields || {},
      data.error?.code || "",
    );
  if (data.csrf_token) csrf = data.csrf_token;
  return data;
}
export const blank: Content = {
  title: "",
  description: "",
  author: "",
  total_time: null,
  yields: "",
  source_url: null,
  image: "",
  ingredients: [],
  instructions: [],
  notes: "",
};
export const sample: Content = {
  ...blank,
  title: "Lemony chickpeas on toast",
  description:
    "A little pantry magic. Creamy chickpeas, bright lemon, and a good piece of toast. An example to make your own.",
  total_time: 15,
  yields: "2 servings",
  ingredients: [
    "2 tbsp olive oil",
    "2 garlic cloves, thinly sliced",
    "1 can chickpeas, drained",
    "1 lemon, zest and juice",
    "2 thick slices of sourdough",
    "A handful of parsley",
    "Salt and black pepper",
  ],
  instructions: [
    "Warm the olive oil in a pan over medium heat. Add the garlic and stir until fragrant.",
    "Add the chickpeas and a splash of water. Simmer for 5 minutes, then lightly mash some of the chickpeas.",
    "Stir in the lemon zest and juice. Season to taste with salt and black pepper.",
    "Toast the sourdough. Spoon the chickpeas over it and finish with parsley and a drizzle of olive oil.",
  ],
};
export function readLocal<T>(key: string, fallback: T): T {
  try {
    return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
  } catch {
    return fallback;
  }
}
export function writeLocal(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* Storage may be unavailable; in-memory editing continues. */
  }
}

export function recipeContent(c: Content): Content {
  return {
    title: c.title,
    description: c.description,
    author: c.author,
    total_time: c.total_time,
    yields: c.yields,
    source_url: c.source_url,
    image: c.image,
    ingredients: c.ingredients,
    instructions: c.instructions,
    notes: c.notes,
    favorite: c.favorite,
  };
}
