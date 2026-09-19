import { Router, Request, Response } from 'express';
import nodemailer, { Transporter } from 'nodemailer';

const router = Router();

const TO_EMAIL   = process.env.DEMO_REQUEST_TO || 'aeman098.fatima@gmail.com';
const GMAIL_USER = process.env.GMAIL_USER;
const GMAIL_PASS = process.env.GMAIL_APP_PASSWORD;

let transporter: Transporter | null = null;
if (GMAIL_USER && GMAIL_PASS) {
  transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: { user: GMAIL_USER, pass: GMAIL_PASS },
    // Fail fast instead of hanging the request forever if the host's
    // network blocks/filters outbound SMTP (common on free PaaS tiers).
    connectionTimeout: 10_000,
    greetingTimeout: 10_000,
    socketTimeout: 15_000,
  });
}

// Lightweight in-memory rate limit: 3 requests per IP per hour.
// Fine for a low-traffic demo site; resets on redeploy/restart.
const RATE_LIMIT = 3;
const WINDOW_MS = 60 * 60 * 1000;
const hits = new Map<string, number[]>();

function isRateLimited(ip: string): boolean {
  const now = Date.now();
  const recent = (hits.get(ip) || []).filter(t => now - t < WINDOW_MS);
  recent.push(now);
  hits.set(ip, recent);
  return recent.length > RATE_LIMIT;
}

router.post('/', async (req: Request, res: Response) => {
  const { name, email, reason, company } = req.body || {};

  // Honeypot: real users never fill in this hidden field.
  if (company) {
    return res.json({ ok: true });
  }

  if (!name || !String(name).trim() || !email || !String(email).trim()) {
    return res.status(400).json({ error: 'Name and email are required.' });
  }

  const ip = req.ip || req.socket.remoteAddress || 'unknown';
  if (isRateLimited(ip)) {
    return res.status(429).json({ error: 'Too many requests. Please try again later.' });
  }

  if (!transporter) {
    console.error('Demo request received but GMAIL_USER/GMAIL_APP_PASSWORD are not configured.');
    return res.status(500).json({ error: 'Email is not configured on the server.' });
  }

  try {
    await transporter.sendMail({
      from: `"AI Math Tutor" <${GMAIL_USER}>`,
      to: TO_EMAIL,
      replyTo: String(email),
      subject: `Demo request from ${name}`,
      text: [
        `Name: ${name}`,
        `Email: ${email}`,
        `Reason: ${reason ? String(reason) : '(not provided)'}`,
      ].join('\n'),
    });
    res.json({ ok: true });
  } catch (err) {
    console.error('Failed to send demo request email:', err);
    res.status(500).json({ error: 'Could not send your request. Please try again later.' });
  }
});

export default router;
