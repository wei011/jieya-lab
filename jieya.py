#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jieya-lab —— 解压方式科学评级器

一句话：你下班后瘫在床上刷两小时手机，以为是在放松，其实你在给焦虑充值。
这个工具把 17 种常见解压方式按「证据」重新排了个座次，告诉你：
你今天的解压，到底是在还债，还是在借新债。

它把散落在各处的研究结论，折算成一个可比较的「每分钟解压效率」：
  · 音乐疗愈：多项 RCT 荟萃分析显示能显著降焦虑（效应量 SMD 约 -0.4 到 -0.8），
    机制是促多巴胺、压皮质醇——这是效率最高的一档。
  · 刷手机 / 刷负面新闻（doomscrolling）：研究反复证实它抬高皮质醇、
    让神经系统持续戒备，越刷越焦虑——所以它的分数是负的，是「负资产」。
  · 捏捏乐这类解压玩具：能带来即时的触觉安抚，但 2025 年抽检 11 款样品
    有害物质超标率 100%，本工具给它正分的同时打上安全警示。

输入你今天的解压组合和各花了多久，输出：净解压分、每分钟效率排行榜、
哪几项是在偷偷借债的负资产、以及「同样的时间，换成什么更划算」。

用法：
  python3 jieya.py --do "刷手机:60,听歌:20,撸猫:15"
  python3 jieya.py --do "喝酒:40,刷短视频:90" --json
  python3 jieya.py --list          # 看完整证据库

零依赖，纯标准库，不联网。效率分是把文献效应量做的可比映射，
不是精确疗效值；心理长期困扰请找专业心理咨询或精神科。
"""

import argparse
import json
import sys

# ── 解压方式证据库 ──────────────────────────────────────
# (名称, 类别, 每分钟解压分, 起效速度1-5, 证据强度1-5, 备注/替换提示)
# 每分钟解压分：正=真解压，负=负资产（当下爽、事后更焦虑）。
# 分值是把研究里的效应量方向与强度，映射到一个可加总的相对刻度。
METHODS = {
    "音乐疗愈":   (+2.4, 4, 5, "多项RCT荟萃：显著降焦虑，压皮质醇促多巴胺，性价比之王"),
    "听歌":       (+1.8, 5, 4, "音乐疗愈的日常版，戴上耳机就起效（注意别开太大声伤耳）"),
    "快走":       (+2.6, 3, 5, "运动是抗焦虑的硬通货，30分钟中等强度效果堪比部分药物"),
    "运动":       (+2.6, 3, 5, "内啡肽+消耗皮质醇，起效慢但后劲最足"),
    "逛公园":     (+2.5, 3, 5, "亲近自然显著降皮质醇，'绿色处方'有大量证据"),
    "冥想":       (+2.2, 2, 5, "正念呼吸，起效慢、门槛高，但长期改善焦虑基线"),
    "撸猫":       (+2.0, 5, 4, "抚摸宠物降皮质醇升催产素，即时且温柔"),
    "撸狗":       (+2.0, 5, 4, "同上，遛狗还附赠运动分"),
    "倾诉":       (+2.1, 4, 4, "向信任的人说出来，社会支持是最被低估的解压器"),
    "洗热水澡":   (+1.6, 4, 3, "体温骤降助眠+肌肉放松，睡前尤佳"),
    "小睡":       (+1.5, 3, 4, "20分钟内的短睡回血，超过30分钟反而昏沉（别睡成补觉）"),
    "大哭一场":   (+1.4, 5, 3, "情绪泄洪，哭完真的会轻松，别憋着"),
    "涂色手工":   (+1.7, 4, 3, "重复性手作进入心流，转移反刍思维"),
    "捏捏乐":     (+1.0, 5, 2, "⚠️触觉安抚有即时效果，但2025抽检有害物超标率100%，别咬别捂脸"),
    "打游戏":     (+0.6, 5, 2, "心流爽感是真的，但赢了才解压、输了更上头，是把双刃剑"),
    "买买买":     (-0.3, 5, 2, "多巴胺买的是三分钟快乐，账单和后悔是长期负债"),
    "报复性进食": (-0.6, 5, 3, "高糖高脂即时安抚，血糖过山车+愧疚感反噬"),
    "刷手机":     (-1.2, 5, 4, "看似躺平实则皮质醇持续走高，越刷越空虚，典型负资产"),
    "刷短视频":   (-1.4, 5, 4, "算法专挑刺激点，多巴胺阈值被拉高，之后现实更无聊"),
    "刷负面新闻": (-1.8, 5, 5, "doomscrolling：反复刺激皮质醇与反刍，被研究点名的头号负资产"),
    "喝酒":       (-1.5, 4, 4, "酒精先镇静后反弹，半夜焦虑惊醒+睡眠质量崩，负债最狠"),
    "熬夜":       (-2.0, 3, 5, "'报复性熬夜'借的是明天的自己，睡眠负债利滚利"),
}

# 别名，方便用户随口写
ALIAS = {
    "刷抖音": "刷短视频", "刷视频": "刷短视频", "看剧": "刷短视频",
    "散步": "快走", "跑步": "运动", "健身": "运动",
    "听音乐": "听歌", "音乐": "听歌", "养宠物": "撸猫", "吸猫": "撸猫",
    "聊天": "倾诉", "找朋友": "倾诉", "泡澡": "洗热水澡", "午睡": "小睡",
    "购物": "买买买", "吃东西": "报复性进食", "暴食": "报复性进食",
    "喝酒精": "喝酒", "手机": "刷手机", "冥想呼吸": "冥想", "正念": "冥想",
}


def canon(name):
    name = name.strip()
    return ALIAS.get(name, name)


def parse_combo(s):
    """'刷手机:60,听歌:20' → [(名称, 分钟), ...]"""
    items = []
    for chunk in s.replace("，", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" in chunk or "：" in chunk:
            k, v = chunk.replace("：", ":").split(":", 1)
            items.append((canon(k), float(v)))
        else:
            items.append((canon(chunk), 30.0))
    return items


def assess(combo):
    rows, total, total_min, unknown = [], 0.0, 0.0, []
    for name, minutes in combo:
        if name not in METHODS:
            unknown.append(name)
            continue
        rate, speed, evid, note = METHODS[name]
        score = rate * minutes
        total += score
        total_min += minutes
        rows.append({"方式": name, "分钟": minutes, "每分钟效率": rate,
                     "小计": round(score, 1), "起效速度": speed,
                     "证据强度": evid, "备注": note,
                     "负资产": rate < 0})
    rows.sort(key=lambda r: r["小计"], reverse=True)
    debts = [r for r in rows if r["负资产"]]
    return {
        "净解压分": round(total, 1),
        "总时长分钟": total_min,
        "每分钟平均效率": round(total / total_min, 2) if total_min else 0,
        "明细": rows,
        "负资产": debts,
        "未识别": unknown,
    }


def best_swaps(rows, n=3):
    """给负资产项算：同样的时间换成 Top 正资产能多赚多少分。"""
    top = max(METHODS.items(), key=lambda kv: kv[1][0])
    top_name, top_rate = top[0], top[1][0]
    swaps = []
    for r in rows:
        if r["负资产"]:
            gain = (top_rate - r["每分钟效率"]) * r["分钟"]
            swaps.append((r["方式"], r["分钟"], top_name, round(gain, 0)))
    swaps.sort(key=lambda x: x[3], reverse=True)
    return swaps[:n]


def bar(score, width=20):
    """净分可视化条：正绿负红。"""
    mag = min(abs(score) / 60, 1.0)
    n = int(mag * width)
    return ("█" * n).ljust(width)


def render(r):
    L = []
    L.append("=" * 50)
    L.append("        🧘 解压方式科学评级 · 今日结算")
    L.append("=" * 50)
    net = r["净解压分"]
    verdict = ("🟢 今天是真的在充电" if net > 30 else
               "🟡 解压效果一般，勉强回血" if net > 0 else
               "🔴 今天你在给焦虑充值（净负分）")
    L.append(f"  净解压分：{net:+.0f}   {verdict}")
    L.append(f"  {bar(net)}  （{r['总时长分钟']:.0f}分钟 · "
             f"平均每分钟 {r['每分钟平均效率']:+.2f}）")
    L.append("")
    L.append("  📊 效率排行榜（每分钟含金量，从高到低）：")
    for row in r["明细"]:
        flag = "💸" if row["负资产"] else "  "
        L.append(f"   {flag} {row['方式']:<7} {row['分钟']:>4.0f}分 × "
                 f"{row['每分钟效率']:+.1f} = {row['小计']:+6.0f}   {row['备注'][:22]}")
    if r["负资产"]:
        L.append("")
        L.append("  💸 你的负资产（当下爽，事后更焦虑，越'解压'越紧绷）：")
        for d in r["负资产"]:
            L.append(f"     {d['方式']}（{d['分钟']:.0f}分钟）扣了 {abs(d['小计']):.0f} 分")
        swaps = best_swaps(r["明细"])
        L.append("")
        L.append("  🔁 同样的时间，换个活法能多赚：")
        for old, mins, new, gain in swaps:
            L.append(f"     把 {mins:.0f}分钟「{old}」→「{new}」，净赚 +{gain:.0f} 分")
    if r["未识别"]:
        L.append("")
        L.append(f"  ❓ 没收录：{', '.join(r['未识别'])}（用 --list 看全部）")
    L.append("")
    L.append("  🔑 一句话：解压不是'做点什么让自己爽'，是'别在放松时偷偷借债'。")
    L.append("     最贵的解压，是刷完手机的那两小时——它连账单都不给你看。")
    L.append("=" * 50)
    L.append("※ 效率分为文献效应量的可比映射，非精确疗效。长期困扰请就医。")
    return "\n".join(L)


def render_list():
    L = ["解压方式证据库（每分钟效率 · 起效速度 · 证据强度）", "=" * 50]
    for name, (rate, speed, evid, note) in sorted(
            METHODS.items(), key=lambda kv: kv[1][0], reverse=True):
        tag = "💸负资产" if rate < 0 else "✅正资产"
        L.append(f" {tag} {name:<7} 效率{rate:+.1f} 起效{speed}/5 证据{evid}/5")
        L.append(f"          {note}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="解压方式科学评级器")
    ap.add_argument("--do", default="刷手机:60,听歌:20,撸猫:15",
                    help='解压组合，如 "刷手机:60,听歌:20,快走:30"')
    ap.add_argument("--list", action="store_true", help="打印完整证据库")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    a = ap.parse_args()

    if a.list:
        print(render_list())
        return
    r = assess(parse_combo(a.do))
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(render(r))


if __name__ == "__main__":
    main()
