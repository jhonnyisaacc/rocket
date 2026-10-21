const HEX_KEY = /\b(?:0x)?[0-9a-fA-F]{64}\b/g;
const BASE58_SECRET = /\b[1-9A-HJ-NP-Za-km-z]{64,128}\b/g;

export class Secret {
  constructor(private readonly value: string) {}

  reveal(): string {
    return this.value;
  }

  toString(): string {
    return "[redacted]";
  }

  toJSON(): string {
    return "[redacted]";
  }

  [Symbol.for("nodejs.util.inspect.custom")](): string {
    return "[redacted]";
  }
}

export function redactText(input: string, secrets: readonly string[] = []): string {
  let text = input;
  for (const secret of secrets) {
    if (secret.length >= 8) text = text.split(secret).join("[redacted]");
  }
  return text.replace(HEX_KEY, "[redacted]").replace(BASE58_SECRET, "[redacted]");
}

export function redactError(error: unknown, secrets: readonly string[] = []): string {
  const message = error instanceof Error ? error.message : String(error);
  return redactText(message, secrets);
}
