/* Fail before SDK loading or network work. No command execution permission. */
const { spawnSync } = require('node:child_process');
const path = require('node:path');
module.exports = function requireAdmission() {
  const result = spawnSync(process.env.ROCKET_RESEARCH_PYTHON || 'python3',
    ['-c', 'from rocket.research.governance import require_prospective_admission; require_prospective_admission()'],
    { cwd: path.resolve(__dirname, '../..'), env: process.env, stdio: 'inherit' });
  if (result.error || result.status !== 0) {
    console.error('WORKFLOW_BLOCK: valid research admission required');
    process.exit(2);
  }
};
