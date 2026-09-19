import { Router, Request, Response } from 'express';
import { pool } from '../db/pool';

const router = Router();

/** GET /api/srs/:student_id/due — problems due on or before today */
router.get('/:student_id/due', async (req: Request, res: Response) => {
  const { student_id } = req.params;

  try {
    const { rows } = await pool.query(
      `SELECT
         problem_index,
         interval,
         ease_factor,
         repetitions,
         due_date::text AS due_date
       FROM srs_cards
       WHERE student_id = $1 AND due_date <= CURRENT_DATE
       ORDER BY due_date ASC`,
      [student_id]
    );
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

/** GET /api/srs/:student_id — full SRS schedule for this student */
router.get('/:student_id', async (req: Request, res: Response) => {
  const { student_id } = req.params;

  try {
    const { rows } = await pool.query(
      `SELECT
         problem_index,
         interval,
         ease_factor,
         repetitions,
         due_date::text AS due_date,
         CASE WHEN due_date <= CURRENT_DATE THEN true ELSE false END AS due_now
       FROM srs_cards
       WHERE student_id = $1
       ORDER BY due_date ASC`,
      [student_id]
    );
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});

export default router;
