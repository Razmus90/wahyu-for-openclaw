import { spawn } from 'child_process';
import { createInterface } from 'readline';
import * as path from 'path';

const serverScript = path.resolve(process.cwd(), 'src', 'jcodemunch_mcp', 'server.py');
const pythonArgs = [serverScript];

const child = spawn('python', pythonArgs, { stdio: ['pipe', 'pipe', 'pipe'] });

child.stdout.pipe(process.stdout);
child.stderr.pipe(process.stderr);

const rl = createInterface({ input: process.stdin, terminal: false });
rl.on('line', (line) => {
  child.stdin.write(`${line}\n`);
});

child.on('exit', (code) => {
  rl.close();
  process.exit(code ?? 0);
});
