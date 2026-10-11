// PM2-супервизия Celery-процессов (вместо голых screen-сессий): автоперезапуск при падении,
// pm2 save/startup переживает ребут сервера.
//
//   cd /root/multiuser_bot/Scalp_bot
//   pm2 start deploy/ecosystem.celery.config.js && pm2 save
//
// ВНИМАНИЕ: рестарт scalp-engine-* обрывает сопровождение открытых сделок (recovery сессий
// при старте пока нет) — сторож (check_active_trades) пришлёт админам алерт по каждой
// осиротевшей позиции. Перед ручным рестартом проверяйте engine:{id}:load и позиции.
const cwd = "/root/multiuser_bot/Scalp_bot";
const celery = `${cwd}/myvenv/bin/celery`;

const worker = (name, queues, env = {}) => ({
  name,
  cwd,
  script: celery,
  args: `-A celery_app.celery_config worker -Q ${queues} --concurrency=1 --loglevel=info -n ${name}@%h`,
  interpreter: "none",
  env,
  autorestart: true,
  restart_delay: 5000,
  max_restarts: 20,
  min_uptime: 30000,
  // Celery warm shutdown: даём досчитать текущую задачу.
  kill_timeout: 30000,
});

module.exports = {
  apps: [
    worker("scalp-router", "default,trade_user"),
    worker("scalp-engine-0", "trade_engine_0", { CELERY_ENGINE_ID: "0" }),
    worker("scalp-engine-1", "trade_engine_1", { CELERY_ENGINE_ID: "1" }),
    worker("scalp-demo-showcase", "demo_showcase"),
    // Сторож сделок (check_active_trades) — свой воркер, чтобы его не блокировал роутер.
    worker("scalp-watchdog", "watchdog"),
    {
      // Ровно один экземпляр Beat на кластер.
      name: "scalp-beat",
      cwd,
      script: celery,
      args: "-A celery_app.celery_config beat -l info",
      interpreter: "none",
      autorestart: true,
      restart_delay: 5000,
    },
  ],
};
