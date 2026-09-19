import { Request, Response, NextFunction } from 'express';

/**
 * Simple shared-passcode gate for LLM-backed endpoints.
 *
 * When ACCESS_CODE is set, every request must carry a matching
 * X-Access-Code header. This exists purely to stop random internet
 * traffic from burning a publicly-deployed demo's Anthropic/Gemini quota.
 * When ACCESS_CODE is unset (local dev), the gate is a no-op.
 */
export function accessGate(req: Request, res: Response, next: NextFunction) {
  const required = process.env.ACCESS_CODE;
  if (!required) return next();

  const provided = req.header('X-Access-Code');
  if (provided === required) return next();

  res.status(401).json({ error: 'Invalid or missing access code.' });
}
