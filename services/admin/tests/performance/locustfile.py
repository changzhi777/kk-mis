"""
locustfile.py — 性能 / 负载基准（决策 #3 重构 2026-07-13）

启动 admin（:8300）+ 跑 load test：
  locust -f locustfile.py --host=http://127.0.0.1:8300 --headless -u 50 -r 10 -t 30s

覆盖关键 API：
  - 登录（POST /auth/login）— 高频
  - 实时折扣报价（GET /agent/orders/quote）— 决策 #3 新功能
  - 列出区域代理（GET /agent/agents）— 决策 #3 新功能
  - 公开防伪核销（GET /asset/cards/verify/{code}）— 决策 #3 新功能（无需登录）
"""
import os
import time
import random
import string
from locust import HttpUser, task, between, events


def _rand_code(length: int = 64) -> str:
    return "".join(random.choices(string.hexdigits[:16], k=length))


class AdminUser(HttpUser):
    """已登录 admin 用户的负载（VIP 业务相关）"""
    wait_time = between(0.1, 0.5)

    def on_start(self):
        """每个 user 启动时登录拿 token"""
        r = self.client.post(
            "/admin/api/v1/auth/login",
            json={"username": "admin", "password": "admin1234"},
            name="/auth/login",
        )
        if r.status_code == 200:
            self.token = r.json()["access_token"]
        else:
            self.token = None

    @property
    def _h(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @task(5)
    def list_agents(self):
        """列出区域代理（决策 #3 关键路径）"""
        self.client.get(
            "/admin/api/v1/agent/agents",
            headers=self._h,
            name="/agent/agents",
        )

    @task(3)
    def quote_price(self):
        """实时折扣报价（默认 batch_id=1）。

        perf 环境未 seed batch 时接口返回 404，属数据缺失而非接口故障，
        用 catch_response 容忍以免污染失败率（quote 逻辑正确性由 unit test 覆盖）。
        """
        with self.client.get(
            "/admin/api/v1/agent/orders/quote",
            params={"batch_id": 1, "quantity": random.choice([10, 50, 100, 500, 1000])},
            headers=self._h,
            name="/agent/orders/quote",
            catch_response=True,
        ) as r:
            if r.status_code == 404:
                r.success()

    @task(2)
    def list_orders(self):
        """列出订单"""
        self.client.get(
            "/admin/api/v1/agent/orders",
            headers=self._h,
            name="/agent/orders",
        )

    @task(1)
    def yearly_commission(self):
        """查询年度返佣"""
        self.client.get(
            "/admin/api/v1/agent/yearly-commission",
            params={"year": 2026},
            headers=self._h,
            name="/agent/yearly-commission",
        )


class PublicUser(HttpUser):
    """未登录用户（公开防伪核销页）"""
    wait_time = between(0.5, 2.0)

    @task
    def verify_card(self):
        """公开防伪核销（无需登录）"""
        code = _rand_code(64)
        self.client.get(
            f"/admin/api/v1/asset/cards/verify/{code}",
            name="/asset/cards/verify/{code}",
        )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print(f"\n[perf] 启动 locust 负载测试")
    print(f"[perf] host: {environment.host}")
    print(f"[perf] 目标：建立 P95/P99 基线\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """跑完输出 P95/P99 摘要"""
    stats = environment.stats
    total = stats.total
    print(f"\n[perf] === 摘要 ===")
    print(f"[perf] 总请求：{total.num_requests}")
    print(f"[perf] 失败率：{total.fail_ratio * 100:.2f}%")
    print(f"\n[perf] 各端点 P95 / P99 / 平均延迟（ms）：")
    print(f"{'端点':<40} {'P50':>8} {'P95':>8} {'P99':>8} {'avg':>8} {'reqs':>6}")
    for entry in stats.entries.values():
        if entry.num_requests > 0:
            print(
                f"{entry.name[:40]:<40} "
                f"{entry.get_response_time_percentile(0.50):>8.0f} "
                f"{entry.get_response_time_percentile(0.95):>8.0f} "
                f"{entry.get_response_time_percentile(0.99):>8.0f} "
                f"{entry.avg_response_time:>8.0f} "
                f"{entry.num_requests:>6}"
            )
    print()
