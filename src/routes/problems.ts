import { Router, Request, Response } from 'express';
import { spawn } from 'child_process';
import path from 'path';
import dotenv from 'dotenv';

dotenv.config();

const router = Router();
const TUTOR_ROOT  = process.env.TUTOR_ROOT!;
const PYTHON_PATH = process.env.PYTHON_PATH || 'python3';

const PROBLEM_COUNT = 40;

/** GET /api/problems — returns list of { index, question, topic } */
router.get('/', async (_req: Request, res: Response) => {
  const script = `
import sys, json
sys.path.insert(0, '${TUTOR_ROOT}')
from tutor.data.gsm8k_loader import GSM8KLoader
loader = GSM8KLoader()
problems = [{'index': p['index'], 'question': p['question'], 'topic': p['topic']} for p in (loader.get_problem(i) for i in range(${PROBLEM_COUNT}))]
print(json.dumps(problems))
`.trim();

  const child = spawn(PYTHON_PATH, ['-c', script], { cwd: TUTOR_ROOT });
  let stdout = '';
  let stderr = '';

  child.stdout.on('data', (d: Buffer) => { stdout += d.toString(); });
  child.stderr.on('data', (d: Buffer) => { stderr += d.toString(); });

  child.on('close', () => {
    try {
      res.json(JSON.parse(stdout));
    } catch {
      res.status(500).json({ error: 'Failed to load problems', detail: stderr });
    }
  });
});

/**
 * POST /api/problems/detect-methods
 * Bug 2 fix — detect solution methods for any free-form question text (custom problems).
 * Body: { question: string }
 * Response: { methods: string[] }
 * Registered before /:index/methods to avoid Express treating "detect-methods" as an index.
 */
router.post('/detect-methods', async (req: Request, res: Response) => {
  const { question } = req.body as { question?: string };
  if (!question?.trim()) {
    res.status(400).json({ error: 'question is required' });
    return;
  }

  const script = `
import sys, json
sys.path.insert(0, '${TUTOR_ROOT}')
sys.path.insert(0, '${TUTOR_ROOT}/tutor')
from dotenv import load_dotenv
load_dotenv('${TUTOR_ROOT}/tutor/.env')
data = json.loads(sys.stdin.read())
from tutor.core.reference import detect_methods
print(json.dumps({'methods': detect_methods(data['question'])}))
`.trim();

  const child = spawn(PYTHON_PATH, ['-c', script], {
    cwd: TUTOR_ROOT,
    env: { ...process.env },
  });
  let stdout = '';
  let stderr = '';

  child.stdout.on('data', (d: Buffer) => { stdout += d.toString(); });
  child.stderr.on('data', (d: Buffer) => { stderr += d.toString(); });

  child.stdin.write(JSON.stringify({ question }));
  child.stdin.end();

  child.on('close', () => {
    try {
      res.json(JSON.parse(stdout));
    } catch {
      console.error('[detect-methods] Python error:', stderr);
      res.json({ methods: ['direct'] });
    }
  });
});

/**
 * GET /api/problems/:index/methods
 * Change C — returns the applicable solution methods for a GSM8K problem.
 * Example response: { "methods": ["direct", "algebra", "unit_rate"] }
 */
router.get('/:index/methods', async (req: Request, res: Response) => {
  const index = parseInt(req.params.index, 10);
  if (isNaN(index) || index < 0) {
    res.status(400).json({ error: 'Invalid problem index' });
    return;
  }

  const script = `
import sys, json
sys.path.insert(0, '${TUTOR_ROOT}')
sys.path.insert(0, '${TUTOR_ROOT}/tutor')
from dotenv import load_dotenv
load_dotenv('${TUTOR_ROOT}/tutor/.env')
from tutor.data.gsm8k_loader import GSM8KLoader
from tutor.core.reference import detect_methods
loader = GSM8KLoader()
p = loader.get_problem(${index})
methods = detect_methods(p['question'])
print(json.dumps({'methods': methods}))
`.trim();

  const child = spawn(PYTHON_PATH, ['-c', script], {
    cwd: TUTOR_ROOT,
    env: { ...process.env },
  });
  let stdout = '';
  let stderr = '';

  child.stdout.on('data', (d: Buffer) => { stdout += d.toString(); });
  child.stderr.on('data', (d: Buffer) => { stderr += d.toString(); });

  child.on('close', () => {
    try {
      res.json(JSON.parse(stdout));
    } catch {
      console.error('[detect-methods] Python error:', stderr);
      res.json({ methods: ['direct'] });
    }
  });
});

export default router;
