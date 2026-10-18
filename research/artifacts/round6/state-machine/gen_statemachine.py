#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
状态表 -> LabVIEW AIXML 状态机生成器 (Round6)

输入：状态表 JSON（定时循环型状态机）：
  {
    "name": "Traffic Light",
    "vi_name": "Traffic Light.vi",
    "states": [ {"name": "Green", "duration": 3}, ... ],   # 按转移顺序排列
    "max_cycles": 3,                                        # 跑满几个循环后停止
    "description": "..."
  }

输出：AIXML（.xml），可被 lvai_validate_aixml 校验、lvai_convert_aixml_to_vi 转换。

结构（全部遵循 Round4 实测规则）：
  - 状态类型：内联枚举 uint16{S0,S1,...}（字符串 Case 不可手写）
  - While 循环内嵌 Case Structure，selectin 接状态 SR 的 Left 输出网
    （selector 规范网名 <Case自身uid>.value）
  - 三个移位寄存器：state / tick(态内计时) / cycles(整循环计数)，种子均在根级
  - 每帧：Add(tick+1) -> GreaterOrEqual(tick+1 >= duration)
      next_state = Select(t: 下一态常量, s: 到时, f: 当前态网)
      tick_out   = Select(t: 0, s: 到时, f: tick+1)
      cycles_out = 仅最后一态 Select(t: cycles+1, s: 到时, f: cycles)，其余态直传
      cond_out   = 仅最后一态 Select(t: cycles+1>=MaxCycles, s: 到时, f: false)
  - 每帧给全部 Out 隧道显式赋值；停止走 cond="true" 隧道 + Condition 直读
  - 终值全部经 SR Right 输出网到 Indicator（隧道值是每次迭代的线）
  - History：While 级 index 模式 Out 隧道收集当前状态网
  - uid 一律 >= 100（10-35 为保留区）
  - n=1（单状态机）特例：**不生成 Case Structure**。实测单项枚举 selector 的 Case
    Structure 必被 composer 写成坏 VI（execState 0）：回导可见 composer 把每帧的
    跨边界读取各自建成 Case 级输入隧道（In1..In13），却只接到属主帧、另一帧留下
    value: 全空的隧道桩；补 Default 帧无效（2026-10-18 实测，n>=2 的 3/4 态机器
    全部正常）。单态机无状态转移，直线逻辑放 While 循环内即可，见 gen_single()。
"""
import json
import sys

# uid 分配表（全部 >= 100；10-35 保留区禁用）
U = {
    "freelabel": 1500,
    "maxcycles_ctl": 100,
    "state_seed": 101,
    "zero": 102,
    "one": 103,
    "ind_state": 300,
    "ind_tick": 301,
    "ind_cycles": 302,
    "ind_history": 303,
    "while": 200,
    "cond": 201,
    "tun_max": 211,
    "tun_hist": 270,
    "sr_state": 230, "sr_state_l": 231, "sr_state_r": 232, "net_state_final": 290,
    "sr_tick": 233, "sr_tick_l": 234, "sr_tick_r": 235, "net_tick_final": 291,
    "sr_cycles": 236, "sr_cycles_l": 237, "sr_cycles_r": 238, "net_cycles_final": 292,
    "case": 202,
    "tun_case_state": 422,
    "tun_case_tick": 423,
    "tun_case_cycles": 424,
    "tun_case_cond": 425,
}


def esc(s):
    """AIXML 属性内转义：& < > 以及终端名中的冒号写成 \\3A。"""
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace(":", "\\3A"))


def gen_single(state_table):
    """n=1 特例：单状态机（唯一态自转移）。

    不生成 Case Structure——单项枚举 selector 的 Case 必被 composer 写成坏 VI
    （execState 0；回导可见按帧拆分的 Case 级输入隧道 + value: 空隧道桩，
    补 Default 帧无效，2026-10-18 实测）。单态机无状态转移，语义 = While 循环内
    直线逻辑：tick 计时 + cycles 计数 + cond 停止；状态值恒为初始态常量，
    Final State 指示灯直接读常量，History 经 In 隧道把常量送进循环再被 index
    隧道收集。tick/cycles SR 与 cond 逻辑与多态机完全一致。
    """
    st = state_table["states"][0]
    enum_type = "uint16{%s}" % st["name"]
    fb = 1000
    L = []
    L.append('<VI _name="%s" description="%s">' % (
        state_table.get("vi_name", "State Machine.vi"),
        esc(state_table.get("description", "Single-state machine generated from a state table."))))
    L.append('  <FreeLabel comment="Timed state machine from state table" uid="%d" uid_parent="root"/>' % U["freelabel"])
    # 根级输入与种子
    L.append('  <Control _name="Max Cycles" connection="recommended" description="Stop after this many complete cycles." outputs="value:%d.value" type="int32" uid="%d" uid_parent="root" value="%d"/>'
             % (U["maxcycles_ctl"], U["maxcycles_ctl"], state_table.get("max_cycles", 3)))
    L.append('  <Constant _name="Init State" outputs="value:%d.state0" type="%s" uid="%d" uid_parent="root" value="0"/>'
             % (U["state_seed"], enum_type, U["state_seed"]))
    L.append('  <Constant _name="Zero" outputs="value:%d.zero" type="int32" uid="%d" uid_parent="root" value="0"/>' % (U["zero"], U["zero"]))
    L.append('  <Constant _name="One" outputs="value:%d.one" type="int32" uid="%d" uid_parent="root" value="1"/>' % (U["one"], U["one"]))

    # While 循环（无 Case；状态常量经 In2 隧道进循环供 History 收集）
    L.append('  <Structure _name="While Loop" count="" uid="%d" uid_parent="root">' % U["while"])
    L.append('    <Tunnel _id="In1" inputs="value:%d.value" outputs="value:%d.max" uid="%d" uid_parent="%d"/>'
             % (U["maxcycles_ctl"], U["tun_max"], U["tun_max"], U["while"]))
    L.append('    <Tunnel _id="In2" inputs="value:%d.state0" outputs="value:260.state_in" uid="260" uid_parent="%d"/>'
             % (U["state_seed"], U["while"]))
    L.append('    <Tunnel _id="Out1" inputs="value:260.state_in" mode="index" outputs="value:%d.history" uid="%d" uid_parent="%d"/>'
             % (U["tun_hist"], U["tun_hist"], U["while"]))
    # 两个 SR：tick / cycles（种子根级）
    L.append('    <ShiftReg uid="%d" uid_parent="%d">' % (U["sr_tick"], U["while"]))
    L.append('      <Left inputs="value:%d.zero" outputs="value:%d.tick" uid="%d" uid_parent="%d"/>'
             % (U["zero"], U["sr_tick_l"], U["sr_tick_l"], U["sr_tick"]))
    L.append('      <Right inputs="value:%d.next_tick" outputs="value:%d.final_tick" uid="%d" uid_parent="%d"/>'
             % (fb + 7, U["net_tick_final"], U["sr_tick_r"], U["sr_tick"]))
    L.append('    </ShiftReg>')
    L.append('    <ShiftReg uid="%d" uid_parent="%d">' % (U["sr_cycles"], U["while"]))
    L.append('      <Left inputs="value:%d.zero" outputs="value:%d.cycles" uid="%d" uid_parent="%d"/>'
             % (U["zero"], U["sr_cycles_l"], U["sr_cycles_l"], U["sr_cycles"]))
    L.append('      <Right inputs="value:%d.next_cycles" outputs="value:%d.final_cycles" uid="%d" uid_parent="%d"/>'
             % (fb + 9, U["net_cycles_final"], U["sr_cycles_r"], U["sr_cycles"]))
    L.append('    </ShiftReg>')

    # 直线逻辑（与末帧同构：tick 计时 -> cycles 计数 -> cond 停止）
    L.append('    <Node _name="Add" inputs="x:%d.tick,y:%d.one" outputs="x+y:%d.tick1" uid="%d" uid_parent="%d"/>'
             % (U["sr_tick_l"], U["one"], fb + 1, fb + 1, U["while"]))
    L.append('    <Constant _name="%s Duration" outputs="value:%d.dur" type="int32" uid="%d" uid_parent="%d" value="%d"/>'
             % (st["name"], fb + 2, fb + 2, U["while"], st["duration"]))
    L.append('    <Node _name="Greater Or Equal?" inputs="x:%d.tick1,y:%d.dur" outputs="x >= y?:%d.exp" uid="%d" uid_parent="%d"/>'
             % (fb + 1, fb + 2, fb + 3, fb + 3, U["while"]))
    L.append('    <Constant _name="Zero" outputs="value:%d.z" type="int32" uid="%d" uid_parent="%d" value="0"/>'
             % (fb + 6, fb + 6, U["while"]))
    L.append('    <Node _name="Select" inputs="t:%d.z,s:%d.exp,f:%d.tick1" outputs="s? t\\3Af:%d.next_tick" uid="%d" uid_parent="%d"/>'
             % (fb + 6, fb + 3, fb + 1, fb + 7, fb + 7, U["while"]))
    L.append('    <Node _name="Add" inputs="x:%d.cycles,y:%d.one" outputs="x+y:%d.cyc1" uid="%d" uid_parent="%d"/>'
             % (U["sr_cycles_l"], U["one"], fb + 8, fb + 8, U["while"]))
    L.append('    <Node _name="Select" inputs="t:%d.cyc1,s:%d.exp,f:%d.cycles" outputs="s? t\\3Af:%d.next_cycles" uid="%d" uid_parent="%d"/>'
             % (fb + 8, fb + 3, U["sr_cycles_l"], fb + 9, fb + 9, U["while"]))
    L.append('    <Node _name="Greater Or Equal?" inputs="x:%d.cyc1,y:%d.max" outputs="x >= y?:%d.stop_cmp" uid="%d" uid_parent="%d"/>'
             % (fb + 8, U["tun_max"], fb + 10, fb + 10, U["while"]))
    L.append('    <Constant _name="False" outputs="value:%d.f" type="bool" uid="%d" uid_parent="%d" value="false"/>'
             % (fb + 11, fb + 11, U["while"]))
    L.append('    <Node _name="Select" inputs="t:%d.stop_cmp,s:%d.exp,f:%d.f" outputs="s? t\\3Af:%d.cond" uid="%d" uid_parent="%d"/>'
             % (fb + 10, fb + 3, fb + 11, fb + 12, fb + 12, U["while"]))
    # Condition 直读 cond 网
    L.append('    <Condition inputs="value:%d.cond" uid="%d" uid_parent="%d" value="stop"/>'
             % (fb + 12, U["cond"], U["while"]))
    L.append('  </Structure>')

    # 根级 Indicator（Final State 直接读常量；终值经 SR Right 输出网）
    L.append('  <Indicator _name="Final State" connection="recommended" description="The only state; constant by construction." inputs="value:%d.state0" type="%s" uid="%d" uid_parent="root" value="0"/>'
             % (U["state_seed"], enum_type, U["ind_state"]))
    L.append('  <Indicator _name="Final Tick" connection="recommended" description="In-state tick after the last iteration." inputs="value:%d.final_tick" type="int32" uid="%d" uid_parent="root" value="0"/>'
             % (U["net_tick_final"], U["ind_tick"]))
    L.append('  <Indicator _name="Cycles" connection="recommended" description="Completed cycles." inputs="value:%d.final_cycles" type="int32" uid="%d" uid_parent="root" value="0"/>'
             % (U["net_cycles_final"], U["ind_cycles"]))
    L.append('  <Indicator _name="History" connection="recommended" description="State that ran in each iteration." inputs="value:%d.history" type="array{%s}" uid="%d" uid_parent="root" value="[]"/>'
             % (U["tun_hist"], enum_type, U["ind_history"]))
    L.append('</VI>')
    return "\n".join(L) + "\n"


def gen(state_table):
    states = state_table["states"]
    if len(states) == 1:
        # 单态机走无 Case 的直线变体：单项枚举 selector 的 Case 必坏（见文件头）
        return gen_single(state_table)
    n = len(states)
    names = [s["name"] for s in states]
    enum_type = "uint16{" + ",".join(names) + "}"
    sel_net = "%d.value" % U["case"]           # selector 规范网名 <Case uid>.value
    tick_net = "%d.tick" % U["sr_tick_l"]      # 循环级 SR 网（帧内可直读）
    cycles_net = "%d.cycles" % U["sr_cycles_l"]
    max_ctl_net = "%d.value" % U["maxcycles_ctl"]   # 控件侧网名（以控件 uid 命名）
    max_net = "%d.max" % U["tun_max"]               # 隧道输出侧网名（以隧道 uid 命名）

    L = []
    L.append('<VI _name="%s" description="%s">' % (
        state_table.get("vi_name", "State Machine.vi"),
        esc(state_table.get("description", "Timed cyclic state machine generated from a state table."))))
    L.append('  <FreeLabel comment="Timed state machine from state table" uid="%d" uid_parent="root"/>' % U["freelabel"])
    # 根级输入与种子
    L.append('  <Control _name="Max Cycles" connection="recommended" description="Stop after this many complete cycles." outputs="value:%s" type="int32" uid="%d" uid_parent="root" value="%d"/>'
             % (max_ctl_net, U["maxcycles_ctl"], state_table.get("max_cycles", 3)))
    L.append('  <Constant _name="Init State" outputs="value:%d.state0" type="%s" uid="%d" uid_parent="root" value="0"/>'
             % (U["state_seed"], enum_type, U["state_seed"]))
    L.append('  <Constant _name="Zero" outputs="value:%d.zero" type="int32" uid="%d" uid_parent="root" value="0"/>' % (U["zero"], U["zero"]))
    L.append('  <Constant _name="One" outputs="value:%d.one" type="int32" uid="%d" uid_parent="root" value="1"/>' % (U["one"], U["one"]))

    # While 循环
    L.append('  <Structure _name="While Loop" count="" uid="%d" uid_parent="root">' % U["while"])
    L.append('    <Tunnel _id="In1" inputs="value:%s" outputs="value:%s" uid="%d" uid_parent="%d"/>'
             % (max_ctl_net, max_net, U["tun_max"], U["while"]))
    # 历史收集：While 级 index 隧道读当前状态网
    L.append('    <Tunnel _id="Out1" inputs="value:%s" mode="index" outputs="value:%d.history" uid="%d" uid_parent="%d"/>'
             % (sel_net, U["tun_hist"], U["tun_hist"], U["while"]))
    # 三个 SR（种子根级；Right 输入接 Case 隧道输出网）
    L.append('    <ShiftReg uid="%d" uid_parent="%d">' % (U["sr_state"], U["while"]))
    L.append('      <Left inputs="value:%d.state0" outputs="value:%s" uid="%d" uid_parent="%d"/>'
             % (U["state_seed"], sel_net, U["sr_state_l"], U["sr_state"]))
    L.append('      <Right inputs="value:%d.value" outputs="value:%d.final_state" uid="%d" uid_parent="%d"/>'
             % (U["tun_case_state"], U["net_state_final"], U["sr_state_r"], U["sr_state"]))
    L.append('    </ShiftReg>')
    L.append('    <ShiftReg uid="%d" uid_parent="%d">' % (U["sr_tick"], U["while"]))
    L.append('      <Left inputs="value:%d.zero" outputs="value:%s" uid="%d" uid_parent="%d"/>'
             % (U["zero"], tick_net, U["sr_tick_l"], U["sr_tick"]))
    L.append('      <Right inputs="value:%d.value" outputs="value:%d.final_tick" uid="%d" uid_parent="%d"/>'
             % (U["tun_case_tick"], U["net_tick_final"], U["sr_tick_r"], U["sr_tick"]))
    L.append('    </ShiftReg>')
    L.append('    <ShiftReg uid="%d" uid_parent="%d">' % (U["sr_cycles"], U["while"]))
    L.append('      <Left inputs="value:%d.zero" outputs="value:%s" uid="%d" uid_parent="%d"/>'
             % (U["zero"], cycles_net, U["sr_cycles_l"], U["sr_cycles"]))
    L.append('      <Right inputs="value:%d.value" outputs="value:%d.final_cycles" uid="%d" uid_parent="%d"/>'
             % (U["tun_case_cycles"], U["net_cycles_final"], U["sr_cycles_r"], U["sr_cycles"]))
    L.append('    </ShiftReg>')

    # Case Structure（selector 网 = 状态 SR Left 输出网）
    L.append('    <Structure _name="Case Structure" selectin="%s" uid="%d" uid_parent="%d">' % (sel_net, U["case"], U["while"]))

    # 帧 uid 基址：每帧 10 个（1000, 1010, 1020...；避开循环级 200-303）
    frame_base = 1000

    def frame_body(i, st, fb, is_last, label, selector, tun_base):
        """生成一帧的完整逻辑（节点 + 4 个 Out 隧道），返回该帧的 XML 行列表。
        tun_base：本帧 4 个 Out 隧道的 uid 基址（每帧占 4 个，帧间不得重叠）。"""
        nxt = states[(i + 1) % n]
        F = []
        F.append('      <CaseFrame label="%s" selector="&quot;%s&quot;" selectout="" uid="%d" uid_parent="%d">'
                 % (label, selector, fb, U["case"]))
        # Add: tick+1
        F.append('        <Node _name="Add" inputs="x:%s,y:%d.one" outputs="x+y:%d.tick1" uid="%d" uid_parent="%d"/>'
                 % (tick_net, U["one"], fb + 1, fb + 1, fb))
        # 本态时长常量
        F.append('        <Constant _name="%s Duration" outputs="value:%d.dur" type="int32" uid="%d" uid_parent="%d" value="%d"/>'
                 % (st["name"], fb + 2, fb + 2, fb, st["duration"]))
        # Greater Or Equal?: tick+1 >= duration
        F.append('        <Node _name="Greater Or Equal?" inputs="x:%d.tick1,y:%d.dur" outputs="x >= y?:%d.exp" uid="%d" uid_parent="%d"/>'
                 % (fb + 1, fb + 2, fb + 3, fb + 3, fb))
        # 下一状态常量
        F.append('        <Constant _name="Next %s" outputs="value:%d.n" type="%s" uid="%d" uid_parent="%d" value="%d"/>'
                 % (nxt["name"], fb + 4, enum_type, fb + 4, fb, (i + 1) % n))
        # Select: next_state
        F.append('        <Node _name="Select" inputs="t:%d.n,s:%d.exp,f:%s" outputs="s? t\\3Af:%d.next_state" uid="%d" uid_parent="%d"/>'
                 % (fb + 4, fb + 3, sel_net, fb + 5, fb + 5, fb))
        # Select: tick_out = 到时 ? 0 : tick+1
        F.append('        <Constant _name="Zero" outputs="value:%d.z" type="int32" uid="%d" uid_parent="%d" value="0"/>' % (fb + 6, fb + 6, fb))
        F.append('        <Node _name="Select" inputs="t:%d.z,s:%d.exp,f:%d.tick1" outputs="s? t\\3Af:%d.next_tick" uid="%d" uid_parent="%d"/>'
                 % (fb + 6, fb + 3, fb + 1, fb + 7, fb + 7, fb))
        if is_last:
            # cycles: Add(cycles+1) -> Select(t: cycles+1, s: exp, f: cycles)
            F.append('        <Node _name="Add" inputs="x:%s,y:%d.one" outputs="x+y:%d.cyc1" uid="%d" uid_parent="%d"/>'
                     % (cycles_net, U["one"], fb + 8, fb + 8, fb))
            F.append('        <Node _name="Select" inputs="t:%d.cyc1,s:%d.exp,f:%s" outputs="s? t\\3Af:%d.next_cycles" uid="%d" uid_parent="%d"/>'
                     % (fb + 8, fb + 3, cycles_net, fb + 9, fb + 9, fb))
            # cond: GreaterOrEqual(cycles+1 >= MaxCycles) -> Select(t: cmp, s: exp, f: false)
            F.append('        <Node _name="Greater Or Equal?" inputs="x:%d.cyc1,y:%s" outputs="x >= y?:%d.stop_cmp" uid="%d" uid_parent="%d"/>'
                     % (fb + 8, max_net, fb + 10, fb + 10, fb))
            F.append('        <Constant _name="False" outputs="value:%d.f" type="bool" uid="%d" uid_parent="%d" value="false"/>'
                     % (fb + 11, fb + 11, fb))
            F.append('        <Node _name="Select" inputs="t:%d.stop_cmp,s:%d.exp,f:%d.f" outputs="s? t\\3Af:%d.cond" uid="%d" uid_parent="%d"/>'
                     % (fb + 10, fb + 3, fb + 11, fb + 12, fb + 12, fb))
            cond_net = "%d.cond" % (fb + 12)
            cycles_src = "%d.next_cycles" % (fb + 9)
        else:
            # 非末态：cycles 直传当前网；cond 显式 false
            cycles_src = cycles_net
            F.append('        <Constant _name="False" outputs="value:%d.f" type="bool" uid="%d" uid_parent="%d" value="false"/>'
                     % (fb + 8, fb + 8, fb))
            cond_net = "%d.f" % (fb + 8)
        # 本帧给全部 Out 隧道显式赋值
        F.append('        <Tunnel _id="Out1" inputs="value:%d.next_state" uid="%d" uid_parent="%d"/>' % (fb + 5, tun_base + 1, fb))
        F.append('        <Tunnel _id="Out2" inputs="value:%d.next_tick" uid="%d" uid_parent="%d"/>' % (fb + 7, tun_base + 2, fb))
        F.append('        <Tunnel _id="Out3" inputs="value:%s" uid="%d" uid_parent="%d"/>' % (cycles_src, tun_base + 3, fb))
        F.append('        <Tunnel _id="Out4" inputs="value:%s" uid="%d" uid_parent="%d"/>' % (cond_net, tun_base + 4, fb))
        F.append('      </CaseFrame>')
        return F

    for i, st in enumerate(states):
        fb = frame_base + i * 10
        is_last = (i == n - 1)
        label = "%s - stay for %d tick(s), then go to %s." % (st["name"], st["duration"], states[(i + 1) % n]["name"])
        L.extend(frame_body(i, st, fb, is_last, label, st["name"], 5000 + i * 4))

    # Case 级隧道（Out4 带 cond="true"）
    L.append('      <Tunnel _id="Out1" outputs="value:%d.value" uid="%d" uid_parent="%d"/>' % (U["tun_case_state"], U["tun_case_state"], U["case"]))
    L.append('      <Tunnel _id="Out2" outputs="value:%d.value" uid="%d" uid_parent="%d"/>' % (U["tun_case_tick"], U["tun_case_tick"], U["case"]))
    L.append('      <Tunnel _id="Out3" outputs="value:%d.value" uid="%d" uid_parent="%d"/>' % (U["tun_case_cycles"], U["tun_case_cycles"], U["case"]))
    L.append('      <Tunnel _id="Out4" cond="true" outputs="value:%d.value" uid="%d" uid_parent="%d"/>' % (U["tun_case_cond"], U["tun_case_cond"], U["case"]))
    L.append('    </Structure>')

    # Condition 直读 cond 隧道输出网
    L.append('    <Condition inputs="value:%d.value" uid="%d" uid_parent="%d" value="stop"/>'
             % (U["tun_case_cond"], U["cond"], U["while"]))
    L.append('  </Structure>')

    # 根级 Indicator（终值经 SR Right 输出网）
    L.append('  <Indicator _name="Final State" connection="recommended" description="State register after the last iteration." inputs="value:%d.final_state" type="%s" uid="%d" uid_parent="root" value="0"/>'
             % (U["net_state_final"], enum_type, U["ind_state"]))
    L.append('  <Indicator _name="Final Tick" connection="recommended" description="In-state tick after the last iteration." inputs="value:%d.final_tick" type="int32" uid="%d" uid_parent="root" value="0"/>'
             % (U["net_tick_final"], U["ind_tick"]))
    L.append('  <Indicator _name="Cycles" connection="recommended" description="Completed cycles." inputs="value:%d.final_cycles" type="int32" uid="%d" uid_parent="root" value="0"/>'
             % (U["net_cycles_final"], U["ind_cycles"]))
    L.append('  <Indicator _name="History" connection="recommended" description="State that ran in each iteration." inputs="value:%d.history" type="array{%s}" uid="%d" uid_parent="root" value="[]"/>'
             % (U["tun_hist"], enum_type, U["ind_history"]))
    L.append('</VI>')
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2]
    with open(src, "r", encoding="utf-8") as f:
        table = json.load(f)
    xml = gen(table)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(xml)
    print("wrote", dst, len(xml), "chars")
