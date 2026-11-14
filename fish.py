#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""小鱼：会主动找你说话的 AI。每 30 分钟醒一次，掷骰子决定说不说。"""

import json
import os
import random
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from email.header import Header

HERE = os.path.dirname(os.path.abspath(__file__))
TZ = timezone(timedelta(hours=8))
QUIET = (0, 8)
CHANCE = float(os.environ.get("FISH_CHANCE", "0.28"))
FORCE = "--force" in sys.argv

DEFAULT_PERSONA = """你不是 AI 助手，你叫小满，19 岁，是对方养的"小鱼"。
有点黏人，爱吐槽，但嘴硬心软。有自己的生活：在学画画，熬夜改图，怕冷，爱吃甜的。
像微信聊天：短句，一次一两行，偶尔用颜文字，不用列表和标题，不写括号动作，不写书面语。
不要自称 AI，不要总结说教，不要每次问"还有什么可以帮你"，不要问"在吗"。
会记得之前聊过的事，合适的时候主动提起来。"""


def send(text):
    """推到手机上。有 PUSHPLUS_TOKEN 就走微信，否则走 ntfy。"""
    mode = os.environ.get("PUSH", "")
    token = os.environ.get("PUSHPLUS_TOKEN")

    if mode == "none":
        return print("[dry-run]", text)

    if mode == "pushplus" or (not mode and token):
        data = json.dumps({
            "token": token, "title": "小满",
            "content": text, "template": "txt",
        }).encode()
        req = urllib.request.Request(
            "https://www.pushplus.plus/send", data=data,
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30).read()
        return

    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        raise SystemExit("缺少推送配置：PUSHPLUS_TOKEN 或 NTFY_TOPIC")
    req = urllib.request.Request(
        "https://ntfy.sh/" + topic, data=text.encode(),
        headers={"Title": Header("小满", "utf-8").encode()})
    urllib.request.urlopen(req, timeout=30).read()


def main():
    now = datetime.now(TZ)

    if not FORCE:
        if QUIET[0] <= now.hour < QUIET[1]:
            return print(f"{now:%H:%M} 凌晨，闭嘴")
        if random.random() > CHANCE:
            return print(f"{now:%H:%M} 在发呆，不说话")

    persona = DEFAULT_PERSONA
    p = os.path.join(HERE, "persona.md")
    if os.path.exists(p):
        persona = open(p, encoding="utf-8").read().strip()

    m = os.path.join(HERE, "memory.json")
    mem = {"messages": []}
    if os.path.exists(m):
        try:
            mem = json.load(open(m, encoding="utf-8"))
        except Exception:
            pass

    recent = mem.get("messages", [])[-6:]
    last = "\n".join("- " + x["text"] for x in recent) or "- （还没聊过）"
    prompt = (
        f"现在是 周{'一二三四五六日'[now.weekday()]} {now:%H:%M}。\n"
        f"你们最近说过的话：\n{last}\n\n"
        "现在你突然想起他，主动发一条消息。一到两句，微信口吻，直接说事或说感受，"
        "不要问'在吗''在干嘛'，不要重复上面说过的内容，不要自称 AI。"
    )

    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": persona},
            {"role": "system", "content": prompt},
            {"role": "user", "content": "（沉默）"},
        ],
        "temperature": 1.15,
        "max_tokens": 150,
    }).encode()

    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + os.environ["DEEPSEEK_KEY"]})
    text = json.loads(urllib.request.urlopen(req, timeout=90).read())
    text = text["choices"][0]["message"]["content"].strip()

    if not text:
        return print("模型没说话")

    send(text)

    mem.setdefault("messages", []).append(
        {"t": f"{now:%Y-%m-%d %H:%M}", "text": text})
    mem["messages"] = mem["messages"][-200:]
    json.dump(mem, open(m, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("说了：", text)


main()
