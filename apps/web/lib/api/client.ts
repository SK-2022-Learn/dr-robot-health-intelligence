type Validator<T> = (value: unknown) => value is T;

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export function apiAbsoluteUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
    readonly code: string,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isArrayOf<T>(value: unknown, validator: Validator<T>): value is T[] {
  return Array.isArray(value) && value.every(validator);
}

export function hasString(value: Record<string, unknown>, key: string): boolean {
  return typeof value[key] === "string";
}

function readApiError(value: unknown): { code: string; message: string } | null {
  if (!isRecord(value) || !isRecord(value.error)) return null;
  if (!hasString(value.error, "code") || !hasString(value.error, "message")) return null;
  return { code: value.error.code as string, message: value.error.message as string };
}

function validatedResponse<T>(
  body: unknown,
  status: number,
  ok: boolean,
  validator: Validator<T>,
): T {
  if (!ok) {
    const apiError = readApiError(body);
    throw new ApiClientError(
      apiError?.message ?? `The API request failed with status ${status}.`,
      status,
      apiError?.code ?? "API_ERROR",
    );
  }
  if (!validator(body)) {
    throw new ApiClientError(
      "The API response did not match the expected shape.",
      status,
      "MALFORMED_RESPONSE",
    );
  }
  return body;
}

export async function apiGet<T>(
  path: string,
  validator: Validator<T>,
  signal?: AbortSignal,
  timeoutMs = 5_000,
): Promise<T> {
  let response: Response;
  try {
    const timeoutSignal = AbortSignal.timeout(timeoutMs);
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal,
    });
  } catch {
    throw new ApiClientError(
      "Dr. Robot API is currently unavailable. Start the backend and refresh.",
      null,
      "API_UNAVAILABLE",
    );
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ApiClientError("The API returned an unreadable response.", response.status, "MALFORMED_RESPONSE");
  }

  return validatedResponse(body, response.status, response.ok, validator);
}

export async function apiMutation<T>(
  path: string,
  method: "POST" | "PATCH",
  validator: Validator<T>,
  body?: unknown,
  timeoutMs = 120_000,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch {
    throw new ApiClientError(
      "Dr. Robot API is currently unavailable. Start the backend and refresh.",
      null,
      "API_UNAVAILABLE",
    );
  }

  let responseBody: unknown;
  try {
    responseBody = await response.json();
  } catch {
    throw new ApiClientError(
      "The API returned an unreadable response.",
      response.status,
      "MALFORMED_RESPONSE",
    );
  }
  return validatedResponse(responseBody, response.status, response.ok, validator);
}

export function apiUpload<T>(
  path: string,
  formData: FormData,
  validator: Validator<T>,
  onUploadComplete?: () => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE_URL}${path}`);
    request.setRequestHeader("Accept", "application/json");
    request.timeout = 60_000;
    request.upload.onload = () => onUploadComplete?.();
    request.onerror = () => reject(new ApiClientError(
      "Dr. Robot API is currently unavailable. Start the backend and refresh.",
      null,
      "API_UNAVAILABLE",
    ));
    request.ontimeout = () => reject(new ApiClientError(
      "Document processing timed out. The stored document may still be available after refresh.",
      null,
      "API_TIMEOUT",
    ));
    request.onload = () => {
      let body: unknown;
      try {
        body = JSON.parse(request.responseText) as unknown;
      } catch {
        reject(new ApiClientError(
          "The API returned an unreadable response.",
          request.status,
          "MALFORMED_RESPONSE",
        ));
        return;
      }
      try {
        resolve(validatedResponse(body, request.status, request.status >= 200 && request.status < 300, validator));
      } catch (error) {
        reject(error);
      }
    };
    request.send(formData);
  });
}

export function readableApiError(error: unknown): string {
  return error instanceof ApiClientError
    ? error.message
    : "Something went wrong while loading this information.";
}
