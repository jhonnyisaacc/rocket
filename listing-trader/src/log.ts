import pino from "pino";
import { redactError } from "./redact.js";

export const REDACT_PATHS = [
  "req.headers.authorization",
  "req.headers['x-api-key']",
  "req.headers['0x-api-key']",
  "req.headers['ok-access-key']",
  "req.headers['ok-access-sign']",
  "req.headers['ok-access-passphrase']",
  "req.headers['ok-access-timestamp']",
  "err.config.headers.authorization",
  "err.config.headers['x-api-key']",
  "err.config.headers['0x-api-key']",
  "err.config.headers['ok-access-sign']",
  "err.config.headers['ok-access-passphrase']",
];

export function createLogger(secrets: readonly string[]) {
  return pino({
    redact: { paths: REDACT_PATHS, censor: "[redacted]" },
    serializers: {
      err(error) {
        return { type: error.name, message: redactError(error, secrets) };
      },
    },
  });
}
