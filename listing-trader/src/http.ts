import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { redactError } from "./redact.js";

export async function readJson(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(Buffer.from(chunk));
  if (chunks.length === 0) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

export function sendJson(res: ServerResponse, status: number, body: unknown): void {
  const payload = JSON.stringify(body);
  res.writeHead(status, { "content-type": "application/json" });
  res.end(payload);
}

export function startServer(
  port: number,
  handler: (req: IncomingMessage, res: ServerResponse) => Promise<void>,
  secrets: readonly string[] = [],
): ReturnType<typeof createServer> {
  const server = createServer((req, res) => {
    handler(req, res).catch((error: unknown) => {
      sendJson(res, 500, { error: redactError(error, secrets) });
    });
  });
  server.listen(port);
  return server;
}
