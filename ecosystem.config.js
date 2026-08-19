/**
 * PM2 生态系统配置文件
 * 用于在 Windows / Linux 后台守护运行 Sheen
 *
 * 启动：pm2 start ecosystem.config.js
 * 停止：pm2 stop ecosystem.config.js
 * 重启：pm2 restart ecosystem.config.js
 * 查看日志：pm2 logs sheen
 */

module.exports = {
  apps: [
    {
      name: "sheen",
      script: "venv\\Scripts\\uvicorn.exe",  // Windows 虚拟环境
      // script: "venv/bin/uvicorn",          // Linux/Mac 虚拟环境（取消注释）
      args: "app.main:app --host 0.0.0.0 --port 8000",
      cwd: __dirname,
      interpreter: "python",
      instances: 1,
      exec_mode: "fork",
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      env: {
        NODE_ENV: "production",
        PYTHONPATH: __dirname,
      },
      error_file: "logs/sheen-error.log",
      out_file: "logs/sheen-out.log",
      log_file: "logs/sheen-combined.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
    },
  ],
};