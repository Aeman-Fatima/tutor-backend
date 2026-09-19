import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';

dotenv.config();

import problemsRouter  from './routes/problems';
import attemptRouter   from './routes/attempt';
import historyRouter   from './routes/history';
import srsRouter       from './routes/srs';
import ocrRouter       from './routes/ocr';
import progressRouter  from './routes/progress';
import demoRequestRouter from './routes/demoRequest';
import { accessGate }  from './middleware/accessGate';

const app  = express();
const PORT = process.env.PORT || 3000;

const allowedOrigins = (process.env.CORS_ORIGINS || 'http://localhost:4200')
  .split(',')
  .map(o => o.trim());

app.use(cors({ origin: allowedOrigins }));
app.use(express.json());

app.get('/api/health', (_req, res) => res.json({ ok: true }));

// Public — lets visitors without an access code request a demo.
app.use('/api/demo-request', demoRequestRouter);

app.use(accessGate);

app.use('/api/problems',  problemsRouter);
app.use('/api/attempt',   attemptRouter);
app.use('/api/history',   historyRouter);
app.use('/api/srs',       srsRouter);
app.use('/api/ocr',       ocrRouter);
app.use('/api/progress',  progressRouter);

app.listen(PORT, () => {
  console.log(`Math Tutor backend listening on http://localhost:${PORT}`);
});
