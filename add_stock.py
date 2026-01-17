import os
import re
import time
import requests

def get_telegram_updates(bot_token):
    """获取 Telegram 机器人最近收到的消息"""
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        # timeout=10 避免卡死
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("result", [])
    except Exception as e:
        print(f"获取消息失败: {e}")
    return []

def send_reply(bot_token, chat_id, text):
    """发送回复消息"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=data, timeout=5)
    except:
        pass

def main():
    bot_token = os.getenv("TG_BOT_TOKEN")
    admin_chat_id = os.getenv("TG_CHAT_ID")

    if not bot_token:
        print("❌ 错误：未设置 TG_BOT_TOKEN")
        return

    # 1. 获取消息
    updates = get_telegram_updates(bot_token)
    if not updates:
        print("📭 没有新消息")
        return

    print(f"📥 收到 {len(updates)} 条消息，开始处理...")

    # 2. 读取现有股票列表
    file_path = "stock_list.txt"
    existing_stocks = set()
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            existing_stocks = {line.strip() for line in f if line.strip()}

    # 3. 初始化操作集合
    stocks_to_add = set()
    stocks_to_remove = set()
    latest_update_id = 0
    
    # 状态标记
    should_clear = False 
    should_view = False 

    # 4. 解析消息 (只处理最近 40 分钟)
    current_time = time.time()
    
    for update in updates:
        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")
        date = message.get("date", 0)
        update_id = update.get("update_id")

        latest_update_id = max(latest_update_id, update_id)

        # 安全检查
        if admin_chat_id and chat_id != str(admin_chat_id):
            continue

        # 时间检查
        if current_time - date > 2400: 
            continue

        print(f"  -- 处理消息: {text}")

        # === 预处理：提取消息中的所有股票代码 ===
        # 只要是6位数字都提取出来
        codes_in_msg = re.findall(r"\d{6}", text)

        # === 意图识别 ===
        
        # 1. 识别 [删除] 指令
        # 关键词：删除, 移除, del, delete, rm, remove
        if re.search(r"(删除|移除|del|delete|rm|remove)", text, re.IGNORECASE):
            # 如果消息包含删除词，则该消息里的所有代码都是要删除的
            for code in codes_in_msg:
                stocks_to_remove.add(code)
                print(f"     -> 标记删除: {code}")
        
        # 2. 识别 [清空] 指令
        elif re.search(r"(清空|clear)", text, re.IGNORECASE):
            should_clear = True
            print("     -> 标记清空")
            
        # 3. 识别 [添加] 指令 (默认)
        # 如果不是删除，也不是清空，且包含代码，那就是添加
        elif codes_in_msg:
            for code in codes_in_msg:
                stocks_to_add.add(code)
                print(f"     -> 标记添加: {code}")

        # 4. 识别 [查看] 指令
        if re.search(r"(查看|查询|列表|list|ls|cx)", text, re.IGNORECASE):
            should_view = True

    # 5. 执行列表变更
    list_changed = False
    
    # 只要有任何增删改操作
    if should_clear or stocks_to_add or stocks_to_remove:
        list_changed = True
        
        # 逻辑顺序：先处理清空 -> 再处理添加 -> 最后处理删除
        
        # 1. 确定基准列表
        if should_clear:
            final_list = set()
            action_msg = "🗑 <b>列表已清空。</b>"
        else:
            final_list = existing_stocks.copy()
            action_msg = "✅ <b>列表已更新。</b>"

        # 2. 执行添加
        if stocks_to_add:
            final_list = final_list.union(stocks_to_add)
            action_msg += f"\n➕ 新增: {', '.join(sorted(stocks_to_add))}"

        # 3. 执行删除 (删除优先级最高，防止刚加又不想加了)
        if stocks_to_remove:
            # 只有在列表里的才能删
            removed_actual = set()
            for code in stocks_to_remove:
                if code in final_list:
                    final_list.remove(code)
                    removed_actual.add(code)
            
            if removed_actual:
                action_msg += f"\n➖ 移除: {', '.join(sorted(removed_actual))}"
            else:
                action_msg += f"\n⚠️ 尝试移除 {', '.join(sorted(stocks_to_remove))} 但它们不在列表中"

        # 写入文件
        with open(file_path, "w", encoding="utf-8") as f:
            for stock in sorted(final_list):
                f.write(f"{stock}\n")
        
        # 更新内存数据
        existing_stocks = final_list
        
        send_reply(bot_token, admin_chat_id, action_msg)

    # 6. 执行查看逻辑
    if should_view:
        if existing_stocks:
            sorted_list = sorted(existing_stocks)
            list_str = "\n".join([f"• <code>{code}</code>" for code in sorted_list])
            view_msg = f"📋 <b>当前监控列表 ({len(sorted_list)}只):</b>\n{list_str}"
        else:
            view_msg = "📭 <b>当前监控列表为空。</b>"
            
        send_reply(bot_token, admin_chat_id, view_msg)

    # 7. 标记消息已读
    if latest_update_id > 0:
        try:
            requests.get(f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={latest_update_id + 1}", timeout=5)
        except:
            pass

    if not (list_changed or should_view):
        print("本次运行无有效指令。")

if __name__ == "__main__":
    main()
