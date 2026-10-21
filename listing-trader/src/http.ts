import fastifyAuth from "@fastify/auth";
import rateLimit from "@fastify/rate-limit";
import Fastify, { type FastifyInstance, type FastifyReply, type FastifyRequest } from "fastify";
import { tokenMatches } from "./managed-signer.js";
import { createLogger } from "./log.js";

export const BODY_LIMIT = 32 * 1024;

export const mutatingLimit = { rateLimit: { max: 10, timeWindow: "1 minute" } };

declare module "fastify" {
  interface FastifyInstance {
    verifyBearer: (request: FastifyRequest, reply: FastifyReply) => Promise<void>;
  }
}

export async function buildApp(options: { authToken: string; secrets?: readonly string[]; logger?: boolean }): Promise<FastifyInstance> {
  const app = Fastify({
    bodyLimit: BODY_LIMIT,
    logger: options.logger === false ? false : createLogger(options.secrets ?? []),
  });
  await app.register(rateLimit, { global: true, max: 60, timeWindow: "1 minute" });
  await app.register(fastifyAuth);
  app.decorate("verifyBearer", async function (request: FastifyRequest, reply: FastifyReply) {
    const header = request.headers.authorization;
    const token = typeof header === "string" && header.startsWith("Bearer ") ? header.slice("Bearer ".length) : "";
    if (!token || !tokenMatches(token, options.authToken)) {
      return reply.code(401).send({ error: "unauthorized" });
    }
  });
  app.setErrorHandler((error: unknown, _request, reply) => {
    const status = typeof error === "object" && error !== null && "statusCode" in error && typeof error.statusCode === "number" ? error.statusCode : 500;
    if (status === 413) {
      void reply.code(413).send({ error: "body too large" });
      return;
    }
    if (status === 429) {
      void reply.code(429).send({ error: "rate limit" });
      return;
    }
    if (status >= 400 && status < 500) {
      void reply.code(status).send({ error: "invalid request" });
      return;
    }
    void reply.code(500).send({ error: "internal error" });
  });
  return app;
}
