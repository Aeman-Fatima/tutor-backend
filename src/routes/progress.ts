import { Router, Request, Response } from 'express';
import { spawn } from 'child_process';
import { pool } from '../db/pool';
import dotenv from 'dotenv';

dotenv.config();

const router = Router();
const TUTOR_ROOT = process.env.TUTOR_ROOT!;
const PYTHON_PATH = process.env.PYTHON_PATH || 'python3';
const PROBLEM_COUNT = 40;

/**
 * GET /api/progress/:student_id
 *
 * Returns per-topic progress:
 * [
 *   {
 *     topic: "rate",
 *     problems: [{ index, question, latest_state }],
 *     score: 0.75   // fraction of attempted problems whose latest state is "correct"
 *   },
 *   ...
 * ]
 */
router.get('/:student_id', async (req: Request, res: Response) => {
  const { student_id } = req.params;

  try {
    // 1. Load problem list with topics from Python (same as /api/problems)
    const problems = await loadProblems();

    // 2. Fetch latest attempt state per problem for this student from Postgres
    const { rows: attemptRows } = await pool.query(
      `SELECT DISTINCT ON (problem_index)
         problem_index,
         state
       FROM attempts
       WHERE student_id = $1
       ORDER BY problem_index, id DESC`,
      [student_id]
    );

    const latestState = new Map<number, string>();
    for (const row of attemptRows) {
      latestState.set(row.problem_index, row.state);
    }

    // 3. Group problems by topic and compute per-topic score
    const topicMap = new Map<string, { index: number; question: string; latest_state: string | null }[]>();
    for (const p of problems) {
      if (!topicMap.has(p.topic)) topicMap.set(p.topic, []);
      topicMap.get(p.topic)!.push({
        index: p.index,
        question: p.question,
        latest_state: latestState.get(p.index) ?? null,
      });
    }

    const TOPIC_ORDER = ['rate', 'percentage', 'ratio', 'geometry', 'multi_step_arithmetic'];
    const result = TOPIC_ORDER
      .filter(t => topicMap.has(t))
      .map(topic => {
        const probs = topicMap.get(topic)!;
        const attempted = probs.filter(p => p.latest_state !== null);
        const correct = attempted.filter(p => p.latest_state === 'correct');
        const score = attempted.length > 0 ? correct.length / attempted.length : 0;
        return { topic, problems: probs, score };
      });

    res.json(result);
  } catch (err) {
    console.error('GET /api/progress error:', err);
    res.status(500).json({ error: String(err) });
  }
});

function loadProblems(): Promise<{ index: number; question: string; topic: string }[]> {
  return new Promise((resolve, reject) => {
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
      try { resolve(JSON.parse(stdout)); }
      catch { reject(new Error(`Failed to load problems: ${stderr}`)); }
    });
  });
}

export default router;
