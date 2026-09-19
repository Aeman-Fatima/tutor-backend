import { Router, Request, Response } from 'express';
import { pool } from '../db/pool';
import { callPipeline } from '../python';

const router = Router();

/**
 * POST /api/attempt
 *
 * GSM8K problem body:
 *   { student_id, problem_index, student_attempt, conversation?, method? }
 *
 * Custom problem body (Change B):
 *   { student_id, custom_problem, student_attempt, conversation?, method? }
 */
router.post('/', async (req: Request, res: Response) => {
  const {
    student_id,
    problem_index,
    custom_problem,
    student_attempt,
    conversation,
    method,
  } = req.body as {
    student_id?: string;
    problem_index?: number;
    custom_problem?: string;
    student_attempt?: string;
    conversation?: { student_attempt: string; strategy: string; response: string }[];
    method?: string;
  };

  if (!student_id || (problem_index === undefined && !custom_problem) || !student_attempt) {
    res.status(400).json({
      error: 'student_id, student_attempt, and either problem_index or custom_problem are required',
    });
    return;
  }

  const isCustom = !!custom_problem;

  try {
    const result = await callPipeline({
      student_id,
      ...(isCustom
        ? { custom_problem }
        : { problem_index }),
      student_attempt,
      conversation: conversation ?? [],
      method: method || undefined,
    });

    if (!result.ok) {
      res.status(500).json({ error: result.error, trace: result.trace });
      return;
    }

    // Mirror into Postgres — skip for follow-ups and for custom problems (no SRS card).
    if (!result.srs_skipped && !isCustom) {
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
             interval     = EXCLUDED.interval,
             ease_factor  = EXCLUDED.ease_factor,
             repetitions  = EXCLUDED.repetitions,
             due_date     = EXCLUDED.due_date`,
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
