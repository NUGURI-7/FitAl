"""登录/注册失败限速(2026-08-23 用户定):进程内存滑动窗口,单实例够用。

口径要说在前面:业界标准做法是把计数放 Redis,因为多实例要共享。本项目单容器
单进程,内存字典足够;服务重启计数清零也不算破绽——攻击者手里没有"重启"这个开关。
将来真要多实例,换的是本模块的存储,调用侧不动。

策略:失败才记数,成功即清零;窗口内失败达上限 → 锁定一段时间,锁定期间直接拒绝、
不再核验密码(因而不累加失败次数,不会被越试越久地滚雪球)。
"""

import time
from dataclasses import dataclass

# (桶名, 键) → 该键近期的失败时刻列表(单调递增)
_failures: dict[tuple[str, str], list[float]] = {}

# 字典体积上限:超过就整体清理一次过期项(几十个用户的盘子里够不着,纯保险)
_MAX_KEYS = 10_000


@dataclass(frozen=True)
class Policy:
    max_failures: int  # 窗口内允许的失败次数
    window_sec: float  # 统计窗口
    lock_sec: float  # 达到上限后,自最后一次失败起拒绝多久


# 同一用户名连续失败 5 次 → 锁 5 分钟(2026-08-23 用户定)
LOGIN_USER = Policy(max_failures=5, window_sec=300, lock_sec=300)
# 同一来源 IP 每 15 分钟最多 20 次失败:挡"一个来源横扫多个账号"
LOGIN_IP = Policy(max_failures=20, window_sec=900, lock_sec=900)
# 注册按 IP 限:挡邀请码暴力猜
REGISTER_IP = Policy(max_failures=10, window_sec=3600, lock_sec=3600)
# 改密码时核验旧密码同样可被慢慢试(需持有效令牌,但不限等于敞着):同登录口径
CHANGE_PASSWORD = Policy(max_failures=5, window_sec=300, lock_sec=300)


def _prune(hits: list[float], window_sec: float, now: float) -> list[float]:
    return [t for t in hits if now - t < window_sec]


def retry_after(
    bucket: str, key: str, policy: Policy, *, now: float | None = None
) -> int:
    """还要等几秒才能再试;0 表示当前没被限。"""
    now = time.monotonic() if now is None else now
    hits = _prune(_failures.get((bucket, key), []), policy.window_sec, now)
    if len(hits) < policy.max_failures:
        return 0
    remaining = hits[-1] + policy.lock_sec - now
    return max(int(remaining) + 1, 0)


def record_failure(
    bucket: str, key: str, policy: Policy, *, now: float | None = None
) -> None:
    now = time.monotonic() if now is None else now
    if len(_failures) > _MAX_KEYS:
        _sweep(now)
    hits = _prune(_failures.get((bucket, key), []), policy.window_sec, now)
    hits.append(now)
    _failures[(bucket, key)] = hits


def clear(bucket: str, key: str) -> None:
    """登录成功即清零:手滑输错几次不留痕。"""
    _failures.pop((bucket, key), None)


def _sweep(now: float) -> None:
    longest = max(p.window_sec for p in (LOGIN_USER, LOGIN_IP, REGISTER_IP))
    for k, hits in list(_failures.items()):
        if not hits or now - hits[-1] >= longest:
            del _failures[k]


def reset_all() -> None:
    """仅测试用:清空全部计数。"""
    _failures.clear()
