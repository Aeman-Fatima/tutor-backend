/**
 * Calls the Python pipeline via cli_wrapper.py.
 * Spawns a child process, writes JSON to its stdin, reads JSON from stdout.
 *
 * ASSUMPTION: TUTOR_ROOT and PYTHON_PATH are set in backend/.env
 */

import { spawn } from 'child_process';
import path from 'path';
import dotenv from 'dotenv';

dotenv.config();

const TUTOR_ROOT = process.env.TUTOR_ROOT;
const PYTHON_PATH = process.env.PYTHON_PATH || 'python3';

if (!TUTOR_ROOT) {
  throw new Error('TUTOR_ROOT is not set. Copy backend/.env.example → backend/.env and fill it in.');
}

export interface ConversationEntry {
  student_attempt: string;
  strategy: string;
  response: string;
}

export interface PipelineRequest {
  student_id: string;
  problem_index: number;
  student_attempt: string;
  conversation?: ConversationEntry[];
}

export interface SrsCard {
  interval: number;
  ease_factor: number;
  repetitions: number;
  due_date: string;
}

export interface PipelineResult {
  ok: true;
  question: string;
  reference: { steps: string[]; answer: string };
  classification: { state: string; weak_step: string | null; reasoning: string; is_followup: boolean };
  strategy: string;
  response: string;
  srs_card: SrsCard;
  srs_skipped?: boolean;
}

export interface PipelineError {
  ok: false;
  error: string;
  trace?: string;
}

export function callPipeline(req: PipelineRequest): Promise<PipelineResult | PipelineError> {
  return new Promise((resolve, reject) => {
    const wrapperPath = path.join(TUTOR_ROOT!, 'tutor', 'cli_wrapper.py');

    const child = spawn(PYTHON_PATH, ['-u', wrapperPath], {
      cwd: TUTOR_ROOT,
      env: { ...process.env },
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk: Buffer) => { stdout += chunk.toString(); });
    child.stderr.on('data', (chunk: Buffer) => { stderr += chunk.toString(); });

    child.on('close', (code) => {
      if (!stdout.trim()) {
        reject(new Error(`Python process exited with code ${code}. stderr: ${stderr}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout) as PipelineResult | PipelineError);
      } catch {
        reject(new Error(`Failed to parse Python output: ${stdout}. stderr: ${stderr}`));
      }
    });

    child.on('error', (err) => reject(err));

    child.stdin.write(JSON.stringify(req));
    child.stdin.end();
  });
}
