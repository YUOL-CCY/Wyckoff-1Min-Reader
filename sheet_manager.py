import os
import json
import gspread

class SheetManager:
    def __init__(self):
        print("   >>> 初始化 Google Sheets 连接 (GSpread 原生版)...")
        
        # 1. 读取配置
        json_str = os.getenv("GCP_SA_KEY")
        sheet_key = os.getenv("SHEET_NAME") # 这里填表格 ID
        
        if not json_str:
            raise ValueError("❌ 错误: 环境变量 GCP_SA_KEY 为空")
        if not sheet_key:
            raise ValueError("❌ 错误: 环境变量 SHEET_NAME 为空")

        # 2. 解析 JSON
        try:
            creds_dict = json.loads(json_str)
        except json.JSONDecodeError:
            raise ValueError("❌ GCP_SA_KEY 格式错误，请检查 GitHub Secret")

        # 3. 连接 (这是解决 Response [200] 的关键)
        # 不要用 oauth2client，直接把字典传给 gspread
        try:
            self.client = gspread.service_account_from_dict(creds_dict)
            print("   ✅ 认证成功")
        except Exception as e:
            raise Exception(f"认证失败: {e}")

        # 4. 打开表格 (通过 ID)
        try:
            print(f"   >>> 正在打开表格 ID: {sheet_key[:5]}...")
            self.sheet = self.client.open_by_key(sheet_key).sheet1
            print("   ✅ 表格连接成功！")
        except Exception as e:
            print(f"   ❌ 无法打开表格。请确认：")
            print(f"   1. SHEET_NAME 填的是 Spreadsheet ID (不是网址，也不是文件名)")
            print(f"   2. 机器人邮箱已添加为编辑者: {creds_dict.get('client_email')}")
            raise e

    def get_all_stocks(self):
        """读取所有股票"""
        try:
            return self._parse_records(self.sheet.get_all_records())
        except Exception as e:
            print(f"⚠️ 读取失败: {e}")
            return {}

    def _parse_records(self, records):
        """解析数据辅助函数"""
        from datetime import datetime
        stocks = {}
        for row in records:
            # 兼容处理列名
            code_key = next((k for k in row.keys() if 'Code' in str(k)), None)
            if not code_key: continue

            code = str(row[code_key]).strip()
            if code and code.isdigit():
                date = str(row.get('BuyDate', '')).strip() or datetime.now().strftime("%Y-%m-%d")
                qty = str(row.get('Qty', '')).strip() or "0"
                price = str(row.get('Price', '')).strip() or "0.0"
                stocks[code] = {'date': date, 'qty': qty, 'price': price}
        return stocks

    def add_or_update_stock(self, code, date=None, qty=None, price=None):
        from datetime import datetime
        code = str(code)
        date = date or datetime.now().strftime("%Y-%m-%d")
        qty = qty or 0
        price = price or 0.0
        
        try:
            cell = self.sheet.find(code)
            self.sheet.update_cell(cell.row, 2, date)
            self.sheet.update_cell(cell.row, 3, qty)
            self.sheet.update_cell(cell.row, 4, price)
            return "Updated"
        except gspread.exceptions.CellNotFound:
            self.sheet.append_row([code, date, qty, price])
            return "Added"

    def remove_stock(self, code):
        try:
            cell = self.sheet.find(str(code))
            self.sheet.delete_rows(cell.row)
            return True
        except gspread.exceptions.CellNotFound:
            return False

    def clear_all(self):
        self.sheet.resize(rows=1) 
        self.sheet.resize(rows=100)
