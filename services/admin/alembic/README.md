# Alembic 快速参考

在 `services/admin/` 目录执行：

```bash
alembic upgrade head
alembic downgrade -1
```

## 注意事项

- 生产 PostgreSQL 执行迁移前必须先备份数据库，并在生产数据副本上演练 `upgrade → downgrade → upgrade`。
- `.env` 中的数据库配置必须与 admin 服务一致；Alembic 直接复用 `app.config.settings.database_url`。
- `app.db.init_db()` 中的 `Base.metadata.create_all()` 只会创建缺失的表，不会修改已有表或迁移列。已有数据库的结构变更以 Alembic revision 为准。
- 新环境建议先执行 `alembic upgrade head`，再启动应用；`create_all()` 仅作为当前兼容兜底，不能替代迁移。
