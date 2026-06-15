import { Router, Request, Response } from 'express';
import { pool } from '../db/pool';

const router = Router();

/** GET /api/history/:student_id/:problem_index */
router.get('/:student_id/:problem_index', async (req: Request, res: Response) => {
  const { student_id, problem_index } = req.params;
  const idx = parseInt(problem_index, 10);

  if (isNaN(idx)) {
    res.status(400).json({ error: 'problem_index must be an integer' });
    return;
  }

  try {
    const { rows } = await pool.query(
      `SELECT state, timestamp
       FROM attempts
       WHERE student_id = $1 AND problem_index = $2
       ORDER BY id ASC`,
      [student_id, idx]
    );
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

export default router;
