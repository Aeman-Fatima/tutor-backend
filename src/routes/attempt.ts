import { Router, Request, Response } from 'express';
import { pool } from '../db/pool';
import { callPipeline } from '../python';

const router = Router();

/**
 * POST /api/attempt
 * Body: {
 *   student_id:      string,
 *   problem_index:   number,
 *   student_attempt: string,
 *   conversation?:   [{ student_attempt, strategy, response }, ...]  ← optional, pass [] or omit for first turn
 * }
 */
router.post('/', async (req: Request, res: Response) => {
  const { student_id, problem_index, student_attempt, conversation } = req.body as {
    student_id?: string;
    problem_index?: number;
    student_attempt?: string;
    conversation?: { student_attempt: string; strategy: string; response: string }[];
  };

  if (!student_id || problem_index === undefined || !student_attempt) {
    res.status(400).json({ error: 'student_id, problem_index, and student_attempt are required' });
    return;
  }

  try {
    const result = await callPipeline({
      student_id,
      problem_index,
      student_attempt,
      conversation: conversation ?? [],
    });

    if (!result.ok) {
      res.status(500).json({ error: result.error, trace: result.trace });
      return;
    }

    // Mirror into Postgres — skip DB writes for follow-up responses (SRS not updated).
    if (!result.srs_skipped) {
      const client = await pool.connect();
      try {
        await client.query('BEGIN');

        await client.query(
          `INSERT INTO attempts (student_id, problem_index, state, timestamp)
           VALUES ($1, $2, $3, NOW())`,
          [student_id, problem_index, result.classification.state]
        );

        const { interval, ease_factor, repetitions, due_date } = result.srs_card;
        await client.query(
          `INSERT INTO srs_cards (student_id, problem_index, interval, ease_factor, repetitions, due_date)
           VALUES ($1, $2, $3, $4, $5, $6)
           ON CONFLICT (student_id, problem_index) DO UPDATE SET
             interval = EXCLUDED.interval,
             ease_factor = EXCLUDED.ease_factor,
             repetitions = EXCLUDED.repetitions,
             due_date = EXCLUDED.due_date`,
          [student_id, problem_index, interval, ease_factor, repetitions, due_date]
        );

        await client.query('COMMIT');
      } catch (dbErr) {
        await client.query('ROLLBACK');
        throw dbErr;
      } finally {
        client.release();
      }
    }

    res.json(result);
  } catch (err) {
    console.error('POST /api/attempt error:', err);
    res.status(500).json({ error: String(err) });
  }
});

export default router;
