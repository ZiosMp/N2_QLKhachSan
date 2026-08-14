"""
gui_report.py
Frame Tkinter cho tab "Báo cáo" - giao diện tiếng Việt theo phong cách
Modern Hotel Management Dashboard (giữ nguyên toàn bộ logic/chức năng cũ).
Lọc theo khoảng ngày, hiển thị thống kê dạng card, xuất báo cáo Excel.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

import statistics_service as rpt_srv


# ============================ BẢNG MÀU & FONT ============================
COLOR_PRIMARY = "#1F4E78"
COLOR_SECONDARY = "#2F75B5"
COLOR_BG = "#F4F7FA"
COLOR_CARD = "#FFFFFF"
COLOR_HEADING = "#1F2937"
COLOR_TEXT = "#374151"
COLOR_SUCCESS = "#16A34A"
COLOR_DANGER = "#DC2626"
COLOR_MUTED_BTN = "#6B7280"
COLOR_BORDER = "#D1D5DB"
COLOR_ROW_ALT = "#F8FAFC"
COLOR_ROW_SELECT = "#DCEBFB"

FONT_FAMILY = "Segoe UI"
FONT_HEADING = (FONT_FAMILY, 10, "bold")
FONT_BODY = (FONT_FAMILY, 10)
FONT_LABEL_MUTED = (FONT_FAMILY, 9, "bold")
FONT_VALUE = (FONT_FAMILY, 16, "bold")

STATUS_LABELS_VI = {"Unpaid": "Chưa thanh toán", "Paid": "Đã thanh toán", "Cancelled": "Đã hủy"}
STATUS_COLORS = {"Unpaid": COLOR_DANGER, "Paid": COLOR_SUCCESS, "Cancelled": COLOR_MUTED_BTN}
PAYMENT_LABELS_VI = {"Cash": "Tiền mặt", "BankTransfer": "Chuyển khoản"}


class ReportFrame(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master, bg=COLOR_BG)
        self._setup_style()
        self._build_filter()
        self._build_summary()
        self._build_table()
        self.load_report()

    # -------------------------------------------------------------
    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab", background=COLOR_CARD, foreground=COLOR_TEXT,
            font=FONT_BODY, padding=(16, 8), borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLOR_PRIMARY), ("active", "#E7EEF5")],
            foreground=[("selected", "#FFFFFF")],
            font=[("selected", FONT_HEADING)],
        )

        style.configure(
            "TCombobox", padding=5, font=FONT_BODY, fieldbackground=COLOR_CARD,
            background=COLOR_CARD, bordercolor=COLOR_BORDER, arrowcolor=COLOR_PRIMARY,
        )
        style.map("TCombobox", bordercolor=[("focus", COLOR_SECONDARY)])

        style.configure(
            "Treeview", font=FONT_BODY, rowheight=28, background=COLOR_CARD,
            fieldbackground=COLOR_CARD, foreground=COLOR_TEXT, borderwidth=0,
        )
        style.configure(
            "Treeview.Heading", font=FONT_HEADING, background=COLOR_PRIMARY,
            foreground="#FFFFFF", relief="flat",
        )
        style.map("Treeview.Heading", background=[("active", COLOR_SECONDARY)])
        style.map(
            "Treeview", background=[("selected", COLOR_ROW_SELECT)],
            foreground=[("selected", COLOR_HEADING)],
        )

        button_specs = {
            "Load": (COLOR_PRIMARY, "#163a5c"),
            "ExportExcel": (COLOR_SUCCESS, "#12793a"),
        }
        for name, (base, active) in button_specs.items():
            style.configure(
                f"{name}.TButton", background=base, foreground="#FFFFFF",
                font=FONT_HEADING, padding=(14, 8), borderwidth=0, focusthickness=0,
            )
            style.map(f"{name}.TButton", background=[("active", active)])

    def _labelframe(self, parent, text):
        return tk.LabelFrame(
            parent, text=text, padx=14, pady=12, bg=COLOR_CARD, fg=COLOR_PRIMARY,
            font=FONT_HEADING, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER,
        )

    def _entry_style(self, master, textvariable, width=15):
        return tk.Entry(
            master, textvariable=textvariable, width=width, font=FONT_BODY,
            fg=COLOR_TEXT, bg=COLOR_CARD, relief="flat", highlightthickness=1,
            highlightbackground=COLOR_BORDER, highlightcolor=COLOR_SECONDARY,
            insertbackground=COLOR_TEXT,
        )

    # -------------------------------------------------------------
    def _build_filter(self):
        outer = tk.Frame(self, bg=COLOR_BG)
        outer.pack(fill="x", padx=12, pady=(12, 8))

        frm = self._labelframe(outer, "Bộ lọc")
        frm.pack(fill="x")

        today = date.today()
        first_of_month = today.replace(day=1)

        tk.Label(frm, text="Từ ngày (YYYY-MM-DD):", bg=COLOR_CARD, fg=COLOR_TEXT,
                 font=FONT_BODY).grid(row=0, column=0, sticky="e", padx=5)
        self.var_from = tk.StringVar(value=str(first_of_month))
        self._entry_style(frm, self.var_from).grid(row=0, column=1, padx=5)

        tk.Label(frm, text="Đến ngày (YYYY-MM-DD):", bg=COLOR_CARD, fg=COLOR_TEXT,
                 font=FONT_BODY).grid(row=0, column=2, sticky="e", padx=5)
        self.var_to = tk.StringVar(value=str(today))
        self._entry_style(frm, self.var_to).grid(row=0, column=3, padx=5)

        ttk.Button(frm, text="Xem báo cáo", style="Load.TButton",
                   command=self.load_report).grid(row=0, column=4, padx=(16, 5))
        ttk.Button(frm, text="Xuất Excel", style="ExportExcel.TButton",
                   command=self.on_export_excel).grid(row=0, column=5, padx=5)

    def _build_summary(self):
        outer = tk.Frame(self, bg=COLOR_BG)
        outer.pack(fill="x", padx=12, pady=(0, 8))

        frm = self._labelframe(outer, "Tổng quan")
        frm.pack(fill="x")

        self.var_revenue = tk.StringVar(value="0")
        self.var_unpaid = tk.StringVar(value="0")
        self.var_bookings = tk.StringVar(value="0")
        self.var_customers = tk.StringVar(value="0")
        self.var_cash = tk.StringVar(value="0")
        self.var_bank = tk.StringVar(value="0")

        cards = [
            ("Tổng doanh thu (đã thu)", self.var_revenue, COLOR_SUCCESS),
            ("Tổng chưa thu", self.var_unpaid, COLOR_DANGER),
            ("Số lượt đặt phòng", self.var_bookings, COLOR_PRIMARY),
            ("Số khách hàng", self.var_customers, COLOR_PRIMARY),
            ("Doanh thu - Tiền mặt", self.var_cash, COLOR_SECONDARY),
            ("Doanh thu - Chuyển khoản", self.var_bank, COLOR_SECONDARY),
        ]
        for i, (label, var, color) in enumerate(cards):
            r, c = divmod(i, 3)
            self._make_stat_card(frm, label, var, color).grid(
                row=r, column=c, sticky="nsew", padx=8, pady=8)
        for c in range(3):
            frm.columnconfigure(c, weight=1)

    def _make_stat_card(self, parent, label_text, var, value_color):
        """Card nhỏ kiểu dashboard: nhãn xám đậm phía trên, giá trị to đậm màu theo loại."""
        card = tk.Frame(
            parent, bg=COLOR_BG, highlightthickness=1,
            highlightbackground=COLOR_BORDER, padx=12, pady=10,
        )
        tk.Label(card, text=label_text, bg=COLOR_BG, fg=COLOR_HEADING,
                 font=FONT_LABEL_MUTED, anchor="w").pack(fill="x")
        tk.Label(card, textvariable=var, bg=COLOR_BG, fg=value_color,
                 font=FONT_VALUE, anchor="w").pack(fill="x", pady=(4, 0))
        return card

    def _build_table(self):
        outer = tk.Frame(self, bg=COLOR_BG)
        outer.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        frm = self._labelframe(outer, "Chi tiết hóa đơn")
        frm.pack(fill="both", expand=True)

        columns = ("id", "booking", "customer", "room", "type", "amount", "status", "payment", "created_at")
        self.tree = ttk.Treeview(frm, columns=columns, show="headings", height=10)
        headers = ["Mã HĐ", "Đặt phòng", "Khách hàng", "Phòng", "Loại phòng",
                   "Số tiền", "Trạng thái", "Thanh toán", "Ngày tạo"]
        widths = [50, 70, 120, 60, 80, 100, 110, 100, 130]
        for col, head, w in zip(columns, headers, widths):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=w, anchor="center")
        self.tree.pack(fill="both", expand=True)

        self.tree.tag_configure("oddrow", background=COLOR_ROW_ALT)
        self.tree.tag_configure("evenrow", background=COLOR_CARD)
        for status, color in STATUS_COLORS.items():
            self.tree.tag_configure(status, foreground=color, font=(FONT_FAMILY, 10, "bold"))

    # -------------------------------------------------------------
    def load_report(self):
        try:
            start = self.var_from.get()
            end = self.var_to.get()
            stats = rpt_srv.get_statistics(start, end)
            rows = rpt_srv.get_invoice_rows(start, end)
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))
            return

        self.var_revenue.set(f"{stats['total_revenue']:,.0f}")
        self.var_unpaid.set(f"{stats['total_unpaid']:,.0f}")
        self.var_bookings.set(stats["total_bookings"])
        self.var_customers.set(stats["total_customers"])
        self.var_cash.set(f"{stats['revenue_by_payment'].get('Cash', 0):,.0f}")
        self.var_bank.set(f"{stats['revenue_by_payment'].get('BankTransfer', 0):,.0f}")

        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, r in enumerate(rows):
            stripe = "evenrow" if i % 2 == 0 else "oddrow"
            self.tree.insert("", "end", tags=(stripe, r["status"]), values=(
                r["id"], r["booking_id"], r["customer_name"], r["room_number"],
                r["room_type"], f"{float(r['amount']):,.0f}",
                STATUS_LABELS_VI.get(r["status"], r["status"]),
                PAYMENT_LABELS_VI.get(r["payment_method"], r["payment_method"]),
                r["created_at"]
            ))

    def on_export_excel(self):
        try:
            path = rpt_srv.export_report_excel(self.var_from.get(), self.var_to.get())
            messagebox.showinfo("Thành công", f"Đã xuất báo cáo: {path}")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Thống kê")
    root.geometry("850x680")
    root.configure(bg=COLOR_BG)
    ReportFrame(root).pack(fill="both", expand=True)
    root.mainloop()
