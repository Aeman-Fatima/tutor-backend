import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';

dotenv.config();

import problemsRouter from './routes/problems';
import attemptRouter  from './routes/attempt';
import historyRouter  from './routes/history';
import srsRouter      from './routes/srs';
import ocrRouter      from './routes/ocr';

const app  = express();
const PORT = process.env.PORT || 3000;

app.use(cors({ origin: 'http://localhost:4200' }));
app.use(express.json());

app.use('/api/problems', problemsRouter);
app.use('/api/attempt',  attemptRouter);
app.use('/api/history',  historyRouter);
app.use('/api/srs',      srsRouter);
app.use('/api/ocr',      ocrRouter);

app.get('/api/health', (_req, res) => res.json({ ok: true }));

app.listen(PORT, () => {
  console.log(`Math Tutor backend listening on http://localhost:${PORT}`);
});
