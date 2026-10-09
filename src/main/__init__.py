# -*- coding: utf-8 -*-
"""AIM 2627 Python Coursework —— 哨兵 Sentry 控制模块（学生骨架）。

你的全部作业都在本文件里：按题面（题面.pdf）各题的规范补全每个标有 TODO 的函数。
- 骨架已提供：Facing / SentryState 枚举、SentryGrid 的构造与只读属性、
  渲染函数 render_frame（demo 用，不进测试）。
- 你要实现：Q1-Q6 与 Bonus 的全部 TODO，以及 SentryGrid 的
  四个方法（current_pos 的 setter、move_forward、turn_left、turn_right）。
- 未实现的函数 raise NotImplementedError：可见测试会自动 skip，
  CI 一开始就是绿的；实现一个，对应测试亮一个。
- `python main.py`（或 PYTHONPATH=src python -m main）可看 ASCII 演示。
"""
import json
from enum import Enum


# ---------------------------------------------------------------------------
# 仿真世界基础（已提供，勿改）
# ---------------------------------------------------------------------------
class Facing(Enum):
    """朝向枚举。世界坐标 (x, y)：x 向右增长，y 向上增长（数学系）。"""

    UP = (0, 1)
    DOWN = (0, -1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)

    @property
    def delta(self):
        """该朝向的单位位移向量 (dx, dy)。"""
        return self.value[0], self.value[1]


# ---------------------------------------------------------------------------
# Q1 机器人自检（题面 Q1·自检状态计算与报告生成）
# ---------------------------------------------------------------------------
def hp_ratio(hp, max_hp):
    """返回 0~100 的健康百分比，按比例四舍五入并做边界钳制。"""
    try:
        hp = float(hp)
        max_hp = float(max_hp)
    except (TypeError, ValueError):
        raise ValueError("hp 和 max_hp 必须为可转换的数字")

    if max_hp <= 0:
        return 0

    pct = (hp / max_hp) * 100.0
    pct = max(0.0, min(100.0, pct))
    return int(round(pct))


def status_report(name, robot_type, hp, max_hp, battery):
    """生成一行自检报告，格式：name | robot_type |HP xx%|BAT yy%|档位。"""
    hp_pct = hp_ratio(hp, max_hp)

    try:
        battery = float(battery)
    except (TypeError, ValueError):
        raise ValueError("battery 必须为可转换的数字")

    bat_pct = max(0.0, min(100.0, battery))
    bat_pct = int(round(bat_pct))

    if bat_pct >= 60:
        status = "OK"
    elif bat_pct >= 20:
        status = "WARNING"
    else:
        status = "LOW"

    return (
        f"{name:<10}| {robot_type:<9}|HP {hp_pct:>3}%|BAT {bat_pct:>3}%|{status}"
    )


# ---------------------------------------------------------------------------
# Q2 战斗日志分析（题面 Q2·多源日志解析与统计）
# ---------------------------------------------------------------------------
def analyze_damage_log(lines):
    """解析混合格式伤害日志，返回总量、按部位统计、最重部位和平均值。"""
    by_armor = {"front": 0, "left": 0, "right": 0}
    total = 0
    seen_ids = set()
    valid_count = 0

    for raw in lines or []:
        if raw is None:
            continue

        line = str(raw).strip()
        if not line or line.startswith("#"):
            continue

        # JSON 形式：{"armor": "front", "damage": 30, "id": 7}
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue

            armor = obj.get("armor")
            damage = obj.get("damage")
            if armor not in by_armor:
                continue

            if "id" in obj:
                obj_id = obj["id"]
                if obj_id in seen_ids:
                    continue
                seen_ids.add(obj_id)

            if isinstance(damage, bool):
                continue
            if isinstance(damage, int):
                dmg = damage
            elif isinstance(damage, float) and damage.is_integer():
                dmg = int(damage)
            else:
                try:
                    dmg = int(damage)
                except (TypeError, ValueError):
                    continue

            if dmg < 0:
                continue

            by_armor[armor] += dmg
            total += dmg
            valid_count += 1
            continue

        # 传感器行：F:32,L:5,R:12
        entries = [part.strip() for part in line.split(",")]
        if not entries:
            continue

        valid_pairs = []
        for part in entries:
            if not part or ":" not in part:
                valid_pairs = None
                break
            left, right = part.split(":", 1)
            key = left.strip().upper()
            value = right.strip()
            if key not in {"F", "L", "R"}:
                valid_pairs = None
                break
            try:
                dmg = int(value)
            except ValueError:
                valid_pairs = None
                break
            if dmg < 0:
                valid_pairs = None
                break
            valid_pairs.append((key, dmg))

        if valid_pairs is None:
            continue

        for key, dmg in valid_pairs:
            armor_key = {"F": "front", "L": "left", "R": "right"}[key]
            by_armor[armor_key] += dmg
            total += dmg
            valid_count += 1

    if valid_count == 0:
        most_hit = None
        avg = 0.0
    else:
        max_damage = max(by_armor.values())
        most_hit = next(armor for armor in ("front", "left", "right")
                        if by_armor[armor] == max_damage)
        avg = total / valid_count

    return {
        "total": total,
        "by_armor": by_armor,
        "most_hit": most_hit,
        "avg": float(avg),
    }


# ---------------------------------------------------------------------------
# Q3 SentryGrid（题面 Q3·载体物理规则）
# ---------------------------------------------------------------------------
class SentryGrid:
    """哨兵仿真载体（构造与只读属性已提供；四个 TODO 方法由你实现）。"""

    def __init__(self, width, height, obstacles, enemy_pos,
                 start_pos=(0, 0), facing=Facing.UP, fuel=100):
        self._width = int(width)
        self._height = int(height)
        if self._width <= 0 or self._height <= 0:
            raise ValueError("地图尺寸必须为正")
        # 障碍坐标存入 set，查询 O(1)——已有实现，勿改。
        self._obstacles = set()
        for ob in obstacles:
            x, y = ob
            self._obstacles.add((int(x), int(y)))
        if not isinstance(enemy_pos, (tuple, list)) or len(enemy_pos) != 2:
            raise TypeError("enemy_pos 需要长度为 2 的 tuple/list")
        self._enemy_pos = self._clamp_cell(enemy_pos)
        if self._enemy_pos in self._obstacles:
            raise ValueError("enemy_pos 不能位于障碍物上")
        if not isinstance(facing, Facing):
            facing = Facing.UP
        self._facing = facing
        self._fuel = int(fuel)
        self._collision_count = 0
        self._pos = self._clamp_cell(start_pos)
        if self._pos in self._obstacles:
            raise ValueError("start_pos 不能位于障碍物上")

    def _clamp_cell(self, cell):
        """已提供：元素转 int 并夹回地图范围（供 __init__ 使用）。"""
        x = int(cell[0])
        y = int(cell[1])
        x = max(0, min(self._width - 1, x))
        y = max(0, min(self._height - 1, y))
        return (x, y)

    # -- 只读属性（已提供，勿改） ------------------------------------------
    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def enemy_pos(self):
        return self._enemy_pos

    @property
    def facing(self):
        return self._facing

    @property
    def fuel(self):
        return self._fuel

    @property
    def collision_count(self):
        return self._collision_count

    @property
    def obstacles(self):
        """障碍集合的只读视图（内部 set 引用，不要修改它）。"""
        return self._obstacles

    @property
    def found_enemy(self):
        return self._pos == self._enemy_pos

    def is_blocked(self, x, y):
        """已提供：坐标是否为障碍或越界（O(1)）。"""
        return ((x, y) in self._obstacles
                or not (0 <= x < self._width and 0 <= y < self._height))

    # -- 你要实现的部分 ------------------------------------------------------
    @property
    def current_pos(self):
        """当前位置 (x, y) 的 tuple。"""
        return self._pos

    @current_pos.setter
    def current_pos(self, value):
        """设置当前位置，要求输入为长度 2 的坐标，并且坐标合法且不撞障碍。"""
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise TypeError("current_pos 必须是长度为 2 的 tuple/list")

        try:
            x = int(value[0])
            y = int(value[1])
        except (TypeError, ValueError):
            raise ValueError("current_pos 坐标必须可转成 int")

        if not (0 <= x < self._width and 0 <= y < self._height):
            raise ValueError("current_pos 超出地图边界")

        if (x, y) in self._obstacles:
            raise ValueError("current_pos 不能落在障碍物上")

        self._pos = (x, y)

    def move_forward(self):
        """朝当前 facing 前进一格；若堵住则记录碰撞并原地不动。"""
        if self._fuel <= 0:
            return self._pos

        dx, dy = self._facing.delta
        nx = self._pos[0] + dx
        ny = self._pos[1] + dy

        if self.is_blocked(nx, ny):
            self._collision_count += 1
            return self._pos

        self.current_pos = (nx, ny)
        self._fuel -= 1
        return self._pos

    def turn_left(self):
        """原地左转 90°，返回新的 Facing（不耗电）。"""
        order = (Facing.UP, Facing.LEFT, Facing.DOWN, Facing.RIGHT)
        idx = order.index(self._facing)
        self._facing = order[(idx + 1) % len(order)]
        return self._facing

    def turn_right(self):
        """原地右转 90°，返回新的 Facing（不耗电）。"""
        order = (Facing.UP, Facing.RIGHT, Facing.DOWN, Facing.LEFT)
        idx = order.index(self._facing)
        self._facing = order[(idx + 1) % len(order)]
        return self._facing


# ---------------------------------------------------------------------------
# Q4 贪心导航（题面 Q4·单步贪心导航策略）
# ---------------------------------------------------------------------------
def next_step_toward(pos, target, obstacles, current_facing=Facing.UP):
    """返回使目标更接近的下一步朝向；若没有合适候选则返回当前朝向。"""
    x, y = pos
    tx, ty = target
    obstacles = set(obstacles)

    def step_for(facing):
        dx, dy = facing.delta
        return (x + dx, y + dy)

    def can_move(facing):
        nx, ny = step_for(facing)
        if (nx, ny) in obstacles:
            return False
        return True

    # 优先考虑更大轴差值；若该轴方向不可用，则退回另一个轴
    dx = abs(tx - x)
    dy = abs(ty - y)

    candidates = []
    if dx >= dy:
        if tx > x:
            candidates.append(Facing.RIGHT)
        elif tx < x:
            candidates.append(Facing.LEFT)
        if ty > y:
            candidates.append(Facing.UP)
        elif ty < y:
            candidates.append(Facing.DOWN)
    else:
        if ty > y:
            candidates.append(Facing.UP)
        elif ty < y:
            candidates.append(Facing.DOWN)
        if tx > x:
            candidates.append(Facing.RIGHT)
        elif tx < x:
            candidates.append(Facing.LEFT)

    # 先选使曼哈顿距离缩短的方向；没有则退回 current_facing
    for facing in candidates:
        if not can_move(facing):
            continue
        nx, ny = step_for(facing)
        before = abs(x - tx) + abs(y - ty)
        after = abs(nx - tx) + abs(ny - ty)
        if after < before:
            return facing

    return current_facing


# ---------------------------------------------------------------------------
# Q5 哨兵决策机（题面 Q5·裁判系统决策规则表）
# ---------------------------------------------------------------------------
class SentryState(Enum):
    """哨兵状态机（已提供，勿改）。"""

    PATROL = "PATROL"
    SUSPECT = "SUSPECT"
    ENGAGE = "ENGAGE"
    RETREAT = "RETREAT"
    RETURN = "RETURN"


def decide(sensor, state, hp, heat):
    """按照 R1-R7 决策表返回 (action, new_state)。"""
    if not isinstance(sensor, dict):
        raise ValueError("sensor 必须是 dict")

    required = ("enemy_frames", "enemy_dist", "robot_type", "max_hp")
    for key in required:
        if key not in sensor:
            raise ValueError(f"sensor 缺少字段: {key}")

    enemy_frames = sensor["enemy_frames"]
    if not isinstance(enemy_frames, (tuple, list)) or not enemy_frames:
        raise ValueError("enemy_frames 必须为非空 tuple/list")
    if any(not isinstance(v, bool) for v in enemy_frames):
        raise ValueError("enemy_frames 中必须全为 bool")

    enemy_dist = sensor["enemy_dist"]
    if enemy_dist is not None:
        if isinstance(enemy_dist, bool):
            raise ValueError("enemy_dist 不能为 bool")
        try:
            enemy_dist = int(enemy_dist)
        except (TypeError, ValueError):
            raise ValueError("enemy_dist 必须为 int 或 None")

    robot_type = sensor["robot_type"]
    if not isinstance(robot_type, str) or robot_type not in {"INFANTRY", "HERO"}:
        raise ValueError("robot_type 必须为 'INFANTRY' 或 'HERO'")

    max_hp = sensor["max_hp"]
    if not isinstance(max_hp, (int, float)) or max_hp <= 0:
        raise ValueError("max_hp 必须为正数")

    if not isinstance(state, SentryState):
        raise ValueError("state 必须是 SentryState")

    try:
        hp_pct = float(hp)
    except (TypeError, ValueError):
        raise ValueError("hp 必须可转换为数字")
    if not 0 <= hp_pct <= 100:
        raise ValueError("hp 必须在 0..100 之间")

    # R1：保命优先
    if hp_pct <= 30:
        return ("RETREAT", SentryState.RETREAT)

    if state is SentryState.RETREAT:
        if hp_pct >= 60:
            return ("RETURN", SentryState.RETURN)
        return ("RETREAT", SentryState.RETREAT)

    if state is SentryState.RETURN:
        return ("MOVE_BASE", SentryState.PATROL)

    if state is SentryState.ENGAGE:
        current_seen = bool(enemy_frames[-1])
        if not current_seen:
            if len(enemy_frames) >= 2 and not any(enemy_frames):
                return ("SCAN", SentryState.SUSPECT)
            return ("HOLD_FIRE", SentryState.ENGAGE)

        if enemy_dist is not None and enemy_dist <= 3:
            return ("SHOOT", SentryState.ENGAGE)
        if robot_type == "HERO":
            return ("MOVE_RIGHT", SentryState.ENGAGE)
        return ("MOVE_LEFT", SentryState.ENGAGE)

    current_seen = bool(enemy_frames[-1])
    if not current_seen:
        if state is SentryState.PATROL:
            return ("PATROL_MOVE", SentryState.PATROL)
        return ("SCAN", SentryState.SUSPECT)

    if len(enemy_frames) >= 2 and enemy_frames[-2] and enemy_frames[-1]:
        if enemy_dist is not None and enemy_dist <= 3:
            return ("SHOOT", SentryState.ENGAGE)
        if robot_type == "HERO":
            return ("MOVE_RIGHT", SentryState.ENGAGE)
        return ("MOVE_LEFT", SentryState.ENGAGE)

    return ("SCAN", SentryState.SUSPECT)


# ---------------------------------------------------------------------------
# Q6 巡逻任务（题面 Q6·巡逻契约与验收阈值）
# ---------------------------------------------------------------------------
def run_patrol(grid, max_steps=500):
    """巡逻主循环：沿着敌方目标前进，直到找到敌人或超时/断电。"""
    if max_steps < 0:
        max_steps = 0

    visited = {grid.current_pos}
    found_enemy = grid.found_enemy
    steps = 0

    while steps < max_steps and not found_enemy and grid.fuel > 0:
        target = grid.enemy_pos
        desired = next_step_toward(grid.current_pos, target, grid.obstacles,
                                   grid.facing)

        if desired is not grid.facing:
            order = [Facing.UP, Facing.RIGHT, Facing.DOWN, Facing.LEFT]
            curr_idx = order.index(grid.facing)
            dest_idx = order.index(desired)
            diff = (dest_idx - curr_idx) % 4
            if diff == 1:
                grid.turn_right()
            elif diff == 2:
                grid.turn_right()
                grid.turn_right()
            elif diff == 3:
                grid.turn_left()

        before = grid.current_pos
        grid.move_forward()
        visited.add(grid.current_pos)
        steps += 1
        found_enemy = grid.found_enemy

        if grid.current_pos == before and not found_enemy:
            # 若前方被挡，继续按当前方向再试一次，避免卡死；
            # 这样在多障碍地图上仍可推进到可行路径。
            desired = next_step_toward(grid.current_pos, target, grid.obstacles,
                                       grid.facing)
            if desired is not grid.facing:
                order = [Facing.UP, Facing.RIGHT, Facing.DOWN, Facing.LEFT]
                curr_idx = order.index(grid.facing)
                dest_idx = order.index(desired)
                diff = (dest_idx - curr_idx) % 4
                if diff == 1:
                    grid.turn_right()
                elif diff == 2:
                    grid.turn_right()
                    grid.turn_right()
                elif diff == 3:
                    grid.turn_left()

        if grid.current_pos == target:
            found_enemy = True
            break

    stats = {
        "steps": steps,
        "collisions": int(grid.collision_count),
        "visited_count": len(visited),
        "found_enemy": bool(found_enemy),
        "success": bool(found_enemy),
    }
    return stats


def report_to_json(stats):
    """以固定顺序序列化巡逻统计，确保 JSON 输出稳定且可比较。"""
    ordered = {
        "steps": int(stats.get("steps", 0)),
        "collisions": int(stats.get("collisions", 0)),
        "visited_count": int(stats.get("visited_count", 0)),
        "found_enemy": bool(stats.get("found_enemy", False)),
        "success": bool(stats.get("success", False)),
    }
    return json.dumps(ordered)


# ---------------------------------------------------------------------------
# Bonus：BFS 全局最短路（题面 Bonus·BFS 语义与排行榜）
# ---------------------------------------------------------------------------
def bfs_path_length(start, target, obstacles):
    """返回从 start 到 target 的最短路径步数；不存在则返回 -1。"""
    if start == target:
        return 0

    blocked = set(obstacles)
    if start in blocked or target in blocked:
        return -1

    queue = [(start, 0)]
    seen = {start}

    while queue:
        pos, dist = queue.pop(0)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (pos[0] + dx, pos[1] + dy)
            if nxt in seen or nxt in blocked:
                continue
            if nxt == target:
                return dist + 1
            seen.add(nxt)
            queue.append((nxt, dist + 1))

    return -1


# ---------------------------------------------------------------------------
# 渲染（已提供，demo 专用，不进测试）
# ---------------------------------------------------------------------------
def render_frame(grid, trail=()):
    """ASCII 渲染一帧战场；trail 为走过的格子集合。返回 list[str]。"""
    trail = set(trail)
    rows = []
    for y in range(grid.height - 1, -1, -1):
        row = []
        for x in range(grid.width): 
            if (x, y) == grid.current_pos:
                row.append("◉")
            elif (x, y) == grid.enemy_pos:
                row.append("▲")
            elif (x, y) in grid.obstacles:
                row.append("█")
            elif (x, y) in trail:
                row.append("·")
            else:
                row.append(".")
        rows.append("".join(row))
    return rows
