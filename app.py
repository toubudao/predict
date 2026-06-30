# -*- coding: utf-8 -*-
"""
预测追踪器 Prediction Tracker
功能：记录预测 -> 定时弹窗验证 -> 统计正确率 -> 复盘失败原因
依赖：仅使用 Python 标准库（tkinter），无需额外安装包
运行：python app.py
"""

import json
import os
import uuid
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "predictions.json")

REASON_CATEGORIES = [
    "信息不足",
    "情绪化判断",
    "外部突发因素",
    "逻辑/分析错误",
    "时机判断错误",
    "其他",
]


def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class PredictionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("预测追踪器 Prediction Tracker")
        self.root.geometry("780x540")
        self.data = load_data()
        self.build_ui()
        self.check_due()  # 启动定时检查循环

    # ---------------- UI 构建 ----------------
    def build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.add_tab = ttk.Frame(notebook)
        self.list_tab = ttk.Frame(notebook)
        self.stats_tab = ttk.Frame(notebook)
        self.review_tab = ttk.Frame(notebook)

        notebook.add(self.add_tab, text="新增预测")
        notebook.add(self.list_tab, text="预测列表")
        notebook.add(self.stats_tab, text="统计")
        notebook.add(self.review_tab, text="复盘")

        self.notebook = notebook
        self.build_add_tab()
        self.build_list_tab()
        self.build_stats_tab()
        self.build_review_tab()

        notebook.bind("<<NotebookTabChanged>>", lambda e: self.refresh_all())
        self.refresh_all()

    def build_add_tab(self):
        frm = self.add_tab
        ttk.Label(frm, text="预测内容：").grid(row=0, column=0, sticky="ne", padx=8, pady=8)
        self.content_text = tk.Text(frm, width=62, height=4)
        self.content_text.grid(row=0, column=1, padx=8, pady=8)

        ttk.Label(frm, text="预测结果\n（你认为会发生什么）：").grid(row=1, column=0, sticky="ne", padx=8, pady=8)
        self.outcome_text = tk.Text(frm, width=62, height=3)
        self.outcome_text.grid(row=1, column=1, padx=8, pady=8)

        ttk.Label(frm, text="多久后验证：").grid(row=2, column=0, sticky="e", padx=8, pady=8)
        dur_frame = ttk.Frame(frm)
        dur_frame.grid(row=2, column=1, sticky="w", padx=8, pady=8)
        self.duration_var = tk.StringVar(value="1")
        self.unit_var = tk.StringVar(value="天")
        ttk.Entry(dur_frame, textvariable=self.duration_var, width=6).pack(side="left")
        ttk.Combobox(
            dur_frame, textvariable=self.unit_var,
            values=["分钟", "小时", "天"], width=6, state="readonly"
        ).pack(side="left", padx=5)

        ttk.Label(frm, text="信心程度 (1-100)：").grid(row=3, column=0, sticky="e", padx=8, pady=8)
        self.confidence_var = tk.StringVar(value="70")
        ttk.Entry(frm, textvariable=self.confidence_var, width=8).grid(row=3, column=1, sticky="w", padx=8, pady=8)

        ttk.Label(frm, text="分类标签（可选，如：股票/天气/比赛）：").grid(row=4, column=0, sticky="e", padx=8, pady=8)
        self.category_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.category_var, width=24).grid(row=4, column=1, sticky="w", padx=8, pady=8)

        ttk.Button(frm, text="添加预测", command=self.add_prediction).grid(row=5, column=1, sticky="w", padx=8, pady=14)

    def build_list_tab(self):
        frm = self.list_tab
        columns = ("content", "outcome", "check_at", "status")
        self.tree = ttk.Treeview(frm, columns=columns, show="headings", height=18)
        headers = {"content": "预测内容", "outcome": "预测结果", "check_at": "验证时间", "status": "状态"}
        widths = {"content": 230, "outcome": 210, "check_at": 140, "status": 80}
        for c in columns:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=widths[c])
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        btn_frame = ttk.Frame(frm)
        btn_frame.pack(pady=6)
        ttk.Button(btn_frame, text="手动验证选中项", command=self.manual_verify).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="删除选中项", command=self.delete_selected).pack(side="left", padx=5)

    def build_stats_tab(self):
        frm = self.stats_tab
        self.stats_label = ttk.Label(frm, text="", font=("Arial", 12), justify="left")
        self.stats_label.pack(padx=12, pady=12, anchor="w")
        ttk.Button(frm, text="刷新统计", command=self.refresh_stats).pack(pady=6)

    def build_review_tab(self):
        frm = self.review_tab
        self.review_text = tk.Text(frm, width=88, height=24, wrap="word")
        self.review_text.pack(padx=8, pady=8, fill="both", expand=True)

    # ---------------- 业务逻辑 ----------------
    def add_prediction(self):
        content = self.content_text.get("1.0", "end").strip()
        outcome = self.outcome_text.get("1.0", "end").strip()
        if not content or not outcome:
            messagebox.showwarning("提示", "请填写预测内容和预测结果")
            return
        try:
            duration = float(self.duration_var.get())
            confidence = int(self.confidence_var.get())
        except ValueError:
            messagebox.showwarning("提示", "时长和信心程度需为数字")
            return

        unit = self.unit_var.get()
        delta = {
            "分钟": timedelta(minutes=duration),
            "小时": timedelta(hours=duration),
            "天": timedelta(days=duration),
        }[unit]
        check_at = datetime.now() + delta

        item = {
            "id": str(uuid.uuid4()),
            "content": content,
            "predicted_outcome": outcome,
            "created_at": datetime.now().isoformat(),
            "check_at": check_at.isoformat(),
            "confidence": confidence,
            "category": self.category_var.get().strip() or "未分类",
            "status": "pending",
            "actual_outcome": "",
            "fail_reason": "",
            "fail_reason_category": "",
        }
        self.data.append(item)
        save_data(self.data)
        messagebox.showinfo("成功", f"预测已添加，将于 {check_at.strftime('%Y-%m-%d %H:%M')} 弹窗提醒你验证")
        self.content_text.delete("1.0", "end")
        self.outcome_text.delete("1.0", "end")
        self.category_var.set("")
        self.refresh_all()

    def refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        status_map = {"pending": "待验证", "correct": "✅正确", "incorrect": "❌错误"}
        for item in sorted(self.data, key=lambda x: x["check_at"]):
            check_at = datetime.fromisoformat(item["check_at"]).strftime("%Y-%m-%d %H:%M")
            self.tree.insert("", "end", iid=item["id"], values=(
                item["content"][:30], item["predicted_outcome"][:30], check_at, status_map[item["status"]]
            ))

    def manual_verify(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在列表中选择一条预测")
            return
        item = next((x for x in self.data if x["id"] == sel[0]), None)
        if item:
            self.verify_prediction(item)

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在列表中选择一条预测")
            return
        if messagebox.askyesno("确认", "确定要删除选中的预测吗？"):
            self.data = [x for x in self.data if x["id"] != sel[0]]
            save_data(self.data)
            self.refresh_all()

    def refresh_stats(self):
        total = len(self.data)
        correct = sum(1 for x in self.data if x["status"] == "correct")
        incorrect = sum(1 for x in self.data if x["status"] == "incorrect")
        pending = sum(1 for x in self.data if x["status"] == "pending")
        finished = correct + incorrect
        accuracy = (correct / finished * 100) if finished else 0

        cat_stats = {}
        for x in self.data:
            if x["status"] in ("correct", "incorrect"):
                cat = x["category"]
                cat_stats.setdefault(cat, {"correct": 0, "incorrect": 0})
                cat_stats[cat][x["status"]] += 1

        lines = [
            f"总预测数：{total}",
            f"待验证：{pending}",
            f"已验证：{finished}（正确 {correct} / 错误 {incorrect}）",
            f"总体正确率：{accuracy:.1f}%",
            "",
            "分类正确率：",
        ]
        if cat_stats:
            for cat, s in cat_stats.items():
                t = s["correct"] + s["incorrect"]
                rate = s["correct"] / t * 100 if t else 0
                lines.append(f"  {cat}：{rate:.1f}%（{s['correct']}/{t}）")
        else:
            lines.append("  暂无已验证的分类数据")

        self.stats_label.config(text="\n".join(lines))

    def refresh_review(self):
        self.review_text.config(state="normal")
        self.review_text.delete("1.0", "end")
        failed = [x for x in self.data if x["status"] == "incorrect"]
        if not failed:
            self.review_text.insert("end", "暂无预测失败记录，继续保持！")
        else:
            reason_count = {}
            for x in failed:
                key = x["fail_reason_category"] or "未分类"
                reason_count[key] = reason_count.get(key, 0) + 1
            self.review_text.insert("end", "=== 失败原因分布（按出现次数排序）===\n")
            for r, c in sorted(reason_count.items(), key=lambda kv: -kv[1]):
                self.review_text.insert("end", f"  {r}：{c} 次\n")
            self.review_text.insert("end", "\n=== 失败详情 ===\n\n")
            for x in failed:
                self.review_text.insert("end", f"【预测】{x['content']}\n")
                self.review_text.insert("end", f"【预测结果】{x['predicted_outcome']}\n")
                self.review_text.insert("end", f"【实际结果】{x['actual_outcome']}\n")
                self.review_text.insert("end", f"【失败原因分类】{x['fail_reason_category']}\n")
                self.review_text.insert("end", f"【具体原因】{x['fail_reason']}\n")
                self.review_text.insert("end", "-" * 60 + "\n")
        self.review_text.config(state="disabled")

    def refresh_all(self):
        self.refresh_list()
        self.refresh_stats()
        self.refresh_review()

    # ---------------- 定时检查与弹窗验证 ----------------
    def check_due(self):
        now = datetime.now()
        for item in self.data:
            if item["status"] == "pending" and datetime.fromisoformat(item["check_at"]) <= now:
                self.verify_prediction(item)
        self.root.after(30000, self.check_due)  # 每30秒检查一次是否有到期的预测

    def verify_prediction(self, item):
        result = messagebox.askyesnocancel(
            "预测验证",
            f"预测内容：{item['content']}\n"
            f"预测结果：{item['predicted_outcome']}\n\n"
            f"这个预测最终是否正确？\n（点击\"取消\"可以稍后再判断）"
        )
        if result is None:
            return  # 用户选择稍后判断，状态保持 pending

        actual = simpledialog.askstring("实际结果", "请简要描述实际发生的情况：") or ""
        item["actual_outcome"] = actual

        if result:
            item["status"] = "correct"
        else:
            item["status"] = "incorrect"
            cat = self.ask_reason_category()
            reason = simpledialog.askstring("失败原因", "请描述这次预测失败的具体原因：") or ""
            item["fail_reason"] = reason
            item["fail_reason_category"] = cat

        save_data(self.data)
        self.refresh_all()

    def ask_reason_category(self):
        win = tk.Toplevel(self.root)
        win.title("选择失败原因分类")
        win.geometry("300x260")
        win.grab_set()
        ttk.Label(win, text="这次预测失败主要属于：").pack(pady=8)
        var = tk.StringVar(value=REASON_CATEGORIES[0])
        for r in REASON_CATEGORIES:
            ttk.Radiobutton(win, text=r, variable=var, value=r).pack(anchor="w", padx=24, pady=3)

        result = {}

        def confirm():
            result["value"] = var.get()
            win.destroy()

        ttk.Button(win, text="确定", command=confirm).pack(pady=10)
        win.wait_window()
        return result.get("value", "其他")


if __name__ == "__main__":
    root = tk.Tk()
    app = PredictionApp(root)
    root.mainloop()
