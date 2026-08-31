export const logger = {
  info: (msg: string, ...args: any[]) => {
    console.log(`[INFO] [${new Date().toLocaleTimeString()}] ${msg}`, ...args);
  },
  success: (msg: string, ...args: any[]) => {
    console.log(`[SUCCESS] [${new Date().toLocaleTimeString()}] ${msg}`, ...args);
  },
  warn: (msg: string, ...args: any[]) => {
    console.warn(`[WARN] [${new Date().toLocaleTimeString()}] ${msg}`, ...args);
  },
  error: (msg: string, ...args: any[]) => {
    console.error(`[ERROR] [${new Date().toLocaleTimeString()}] ${msg}`, ...args);
  },
  step: (stepNum: number, totalSteps: number, title: string) => {
    console.log(`\n========================================`);
    console.log(`STEP ${stepNum}/${totalSteps}: ${title.toUpperCase()}`);
    console.log(`========================================`);
  }
};
