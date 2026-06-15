import { Router, Request, Response } from 'express';
import { spawn } from 'child_process';
import path from 'path';
import dotenv from 'dotenv';

dotenv.config();

const router = Router();
const TUTOR_ROOT = process.env.TUTOR_ROOT!;
const PYTHON_PATH = process.env.PYTHON_PATH || 'python3';

// ASSUMPTION: we expose the first 10 GSM8K training problems.
// Change PROBLEM_COUNT here to expose more.
const PROBLEM_COUNT = 10;

/** GET /api/problems — returns list of { index, question } */
router.get('/', async (_req: Request, res: Response) => {
  const script = `
import sys, json
sys.path.insert(0, '${TUTOR_ROOT}')
from tutor.data.gsm8k_loader import GSM8KLoader
loader = GSM8KLoader()
problems = [{'index': i, 'question': loader.get_problem(i)['question']} for i in range(${PROBLEM_COUNT})]
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

export default router;
