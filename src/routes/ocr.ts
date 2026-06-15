/**
 * POST /api/ocr
 * Accepts a multipart image upload, calls ocr_wrapper.py, returns { text: string }.
 *
 * ASSUMPTION: accepted formats jpg/jpeg/png, max 5 MB (enforced by multer).
 * ASSUMPTION: the temp file is deleted after the Python call completes (success or error).
 */

import { Router, Request, Response } from 'express';
import multer from 'multer';
import path from 'path';
import fs from 'fs';
import os from 'os';
import { spawn } from 'child_process';
import dotenv from 'dotenv';

dotenv.config();

const router = Router();

const TUTOR_ROOT  = process.env.TUTOR_ROOT!;
const PYTHON_PATH = process.env.PYTHON_PATH || 'python3';

const upload = multer({
  dest: os.tmpdir(),
  limits: { fileSize: 5 * 1024 * 1024 },  // 5 MB
  fileFilter: (_req, file, cb) => {
    const allowed = ['image/jpeg', 'image/jpg', 'image/png'];
    if (allowed.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error('Only jpg and png images are accepted'));
    }
  },
});

router.post('/', upload.single('image'), async (req: Request, res: Response) => {
  if (!req.file) {
    res.status(400).json({ error: 'No image file uploaded (field name must be "image")' });
    return;
  }

  const imagePath = req.file.path;

  // Rename to include original extension so mimetypes.guess_type works in Python
  const ext = path.extname(req.file.originalname) || '.jpg';
  const renamedPath = imagePath + ext;

  try {
    fs.renameSync(imagePath, renamedPath);
  } catch {
    // renameSync fails across devices on some systems; fall back to original path
  }

  const finalPath = fs.existsSync(renamedPath) ? renamedPath : imagePath;
  const wrapperPath = path.join(TUTOR_ROOT, 'tutor', 'ocr_wrapper.py');

  const cleanup = () => {
    try { fs.unlinkSync(finalPath); } catch { /* already gone */ }
  };

  try {
    const result = await new Promise<{ ok: boolean; text?: string; error?: string }>(
      (resolve, reject) => {
        const child = spawn(PYTHON_PATH, ['-u', wrapperPath], {
          cwd: TUTOR_ROOT,
          env: { ...process.env },
        });

        let stdout = '';
        let stderr = '';
        child.stdout.on('data', (d: Buffer) => { stdout += d.toString(); });
        child.stderr.on('data', (d: Buffer) => { stderr += d.toString(); });

        child.on('close', () => {
          if (!stdout.trim()) {
            reject(new Error(`OCR process produced no output. stderr: ${stderr}`));
            return;
          }
          try { resolve(JSON.parse(stdout)); }
          catch { reject(new Error(`Could not parse OCR output: ${stdout}`)); }
        });

        child.on('error', reject);

        child.stdin.write(JSON.stringify({ image_path: finalPath }));
        child.stdin.end();
      }
    );

    cleanup();

    if (!result.ok) {
      res.status(500).json({ error: result.error });
      return;
    }

    res.json({ text: result.text });

  } catch (err) {
    cleanup();
    console.error('POST /api/ocr error:', err);
    res.status(500).json({ error: String(err) });
  }
});

export default router;
