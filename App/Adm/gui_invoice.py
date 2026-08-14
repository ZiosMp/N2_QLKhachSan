"""
gui_invoice.py
Frame Tkinter cho tab "Hóa đơn" - giao diện tiếng Việt theo phong cách
Modern Hotel Management Dashboard (giữ nguyên toàn bộ logic/chức năng cũ).

Bố cục: Đặt phòng / Khách hàng / Phòng / Nhận phòng / Trả phòng / Đơn giá phòng /
Phí quá giờ (tự động) / Phí dịch vụ (nhập tay) / Tổng tiền / Trạng thái / Thanh toán
+ nút Tạo / Cập nhật / Xuất / Làm mới + bảng danh sách hóa đơn phía dưới.

QUY TẮC:
- Hóa đơn "Đã thanh toán" (Paid) bị KHÓA hoàn toàn - không sửa được nữa
  (trạng thái, phương thức, phí dịch vụ, nút Cập nhật đều bị vô hiệu hóa).
- Khi còn "Chưa thanh toán", Tổng tiền luôn được tính lại theo giá phòng
  HIỆN TẠI (invoice_service tự JOIN sống, không dùng số cũ đã lưu) - nên nếu
  bên Booking đổi phòng, mở lại hóa đơn này sẽ thấy Tổng tiền tự cập nhật.
"""
import tkinter as tk
from tkinter import ttk, messagebox

import invoice_service as inv_srv


# ============================ BẢNG MÀU & FONT ============================
COLOR_PRIMARY = "#1F4E78"     # xanh navy chuyên nghiệp
COLOR_SECONDARY = "#2F75B5"   # xanh dương hiện đại
COLOR_BG = "#F4F7FA"          # nền chính - trắng xanh nhạt
COLOR_CARD = "#FFFFFF"        # nền các khu vực / card
COLOR_HEADING = "#1F2937"     # màu tiêu đề
COLOR_TEXT = "#374151"        # chữ thông thường
COLOR_SUCCESS = "#16A34A"     # đã thanh toán
COLOR_DANGER = "#DC2626"      # chưa thanh toán / cảnh báo
COLOR_MUTED_BTN = "#6B7280"   # nút phụ / trung tính
COLOR_BORDER = "#D1D5DB"      # viền nhẹ
COLOR_ROW_ALT = "#F8FAFC"     # dòng xen kẽ trong bảng
COLOR_ROW_SELECT = "#DCEBFB"  # dòng được chọn trong bảng
COLOR_ENTRY_READONLY = "#F4F7FA"
COLOR_LOCK_BANNER_BG = "#FEF2F2"

FONT_FAMILY = "Segoe UI"
FONT_TITLE = (FONT_FAMILY, 13, "bold")
FONT_HEADING = (FONT_FAMILY, 10, "bold")
FONT_BODY = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)

# Nhãn hiển thị tiếng Việt <-> giá trị lưu trong DB (giữ nguyên tiếng Anh trong ENUM)
STATUS_LABELS_VI = {
    "Unpaid": "Chưa thanh toán",
    "Paid": "Đã thanh toán",
    "Cancelled": "Đã hủy",
}
STATUS_LABELS_VI_REV = {v: k for k, v in STATUS_LABELS_VI.items()}

STATUS_COLORS = {
    "Unpaid": COLOR_DANGER,
    "Paid": COLOR_SUCCESS,
    "Cancelled": COLOR_MUTED_BTN,
}

PAYMENT_LABELS_VI = {
    "Cash": "Tiền mặt",
    "BankTransfer": "Chuyển khoản",
}
PAYMENT_LABELS_VI_REV = {v: k for k, v in PAYMENT_LABELS_VI.items()}


class InvoiceFrame(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master, bg=COLOR_BG)
        self.bookings_cache = {}     # map "001 - A - Phòng 001" -> booking dict
        self.current_invoice_id = None
        self.is_locked = False       # True khi hóa đơn đang xem đã "Đã thanh toán"
        self._setup_style()
        self._build_form()
        self._build_table()
        self.refresh_bookings()
        self.refresh_table()

    # -------------------------------------------------------------
    # THEME / STYLE
    # -------------------------------------------------------------
    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=COLOR_CARD, foreground=COLOR_TEXT, font=FONT_BODY,
            padding=(16, 8), borderwidth=0,
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
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", COLOR_CARD), ("disabled", COLOR_ENTRY_READONLY)],
            bordercolor=[("focus", COLOR_SECONDARY)],
        )

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
            "Create": (COLOR_SECONDARY, "#255f92"),
            "Update": (COLOR_PRIMARY, "#163a5c"),
            "Export": (COLOR_DANGER, "#b91c1c"),
            "Clear": (COLOR_MUTED_BTN, "#565e69"),
            "Filter": (COLOR_SECONDARY, "#255f92"),
        }
        for name, (base, active) in button_specs.items():
            style.configure(
                f"{name}.TButton", background=base, foreground="#FFFFFF",
                font=FONT_HEADING, padding=(14, 8), borderwidth=0, focusthickness=0,
            )
            style.map(f"{name}.TButton", background=[("active", active)])
        # Style riêng cho nút Cập nhật khi bị khóa (xám nhạt, không phản hồi)
        style.configure(
            "UpdateDisabled.TButton", background="#B9C3CC", foreground="#F3F4F6",
            font=FONT_HEADING, padding=(14, 8), borderwidth=0,
        )

    def _entry_style(self, master, textvariable, readonly=False, width=40):
        entry = tk.Entry(
            master, textvariable=textvariable, width=width, font=FONT_BODY,
            fg=COLOR_TEXT, bg=COLOR_CARD, relief="flat", highlightthickness=1,
            highlightbackground=COLOR_BORDER, highlightcolor=COLOR_SECONDARY,
            readonlybackground=COLOR_ENTRY_READONLY, disabledbackground=COLOR_ENTRY_READONLY,
            insertbackground=COLOR_TEXT,
        )
        if readonly:
            entry.config(state="readonly")
        return entry

    def _labelframe(self, parent, text):
        return tk.LabelFrame(
            parent, text=text, padx=14, pady=12, bg=COLOR_CARD, fg=COLOR_PRIMARY,
            font=FONT_HEADING, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER,
        )

    def _field_label(self, parent, text):
        return tk.Label(parent, text=text, bg=COLOR_CARD, fg=COLOR_TEXT, font=FONT_BODY)

    # -------------------------------------------------------------
    # FORM (phần trên)
    # -------------------------------------------------------------
    def _build_form(self):
        outer = tk.Frame(self, bg=COLOR_BG)
        outer.pack(fill="x", padx=12, pady=(12, 8))

        frm = self._labelframe(outer, "Thông tin hóa đơn")
        frm.pack(fill="x")

        # Banner cảnh báo khi hóa đơn đã khóa (ẩn mặc định)
        self.lbl_lock_banner = tk.Label(
            frm, text="🔒 Hóa đơn đã Đã thanh toán - không thể chỉnh sửa.",
            bg=COLOR_LOCK_BANNER_BG, fg=COLOR_DANGER, font=FONT_HEADING,
            anchor="w", padx=10, pady=6,
        )
        # chỉ pack() khi is_locked=True (xem _apply_lock_state)

        # Đặt phòng
        self._field_label(frm, "Đặt phòng:").grid(row=1, column=0, sticky="e", pady=5, padx=(0, 8))
        self.cbo_booking = ttk.Combobox(frm, width=38, state="readonly", font=FONT_BODY)
        self.cbo_booking.grid(row=1, column=1, sticky="w", pady=5)
        self.cbo_booking.bind("<<ComboboxSelected>>", self.on_booking_selected)

        # Khách hàng (tự điền, readonly)
        self._field_label(frm, "Khách hàng:").grid(row=2, column=0, sticky="e", pady=5, padx=(0, 8))
        self.var_customer = tk.StringVar()
        self._entry_style(frm, self.var_customer, readonly=True).grid(row=2, column=1, sticky="w", pady=5)

        # Phòng
        self._field_label(frm, "Phòng:").grid(row=3, column=0, sticky="e", pady=5, padx=(0, 8))
        self.var_room = tk.StringVar()
        self._entry_style(frm, self.var_room, readonly=True).grid(row=3, column=1, sticky="w", pady=5)

        # Nhận phòng / Trả phòng
        self._field_label(frm, "Nhận phòng:").grid(row=4, column=0, sticky="e", pady=5, padx=(0, 8))
        self.var_checkin = tk.StringVar()
        self._entry_style(frm, self.var_checkin, readonly=True).grid(row=4, column=1, sticky="w", pady=5)

        self._field_label(frm, "Trả phòng:").grid(row=5, column=0, sticky="e", pady=5, padx=(0, 8))
        self.var_checkout = tk.StringVar()
        self._entry_style(frm, self.var_checkout, readonly=True).grid(row=5, column=1, sticky="w", pady=5)

        # Đơn giá phòng - luôn phản ánh giá HIỆN TẠI của phòng đang gắn với booking
        self._field_label(frm, "Đơn giá phòng:").grid(row=6, column=0, sticky="e", pady=5, padx=(0, 8))
        self.var_price = tk.StringVar(value="0")
        self._entry_style(frm, self.var_price, readonly=True).grid(row=6, column=1, sticky="w", pady=5)

        # Phí quá giờ - tự động từ bookings.extra_fee (module Booking tính lúc trả phòng)
        self._field_label(frm, "Phí quá giờ:").grid(row=7, column=0, sticky="e", pady=5, padx=(0, 8))
        self.var_late_fee = tk.StringVar(value="0")
        self._entry_style(frm, self.var_late_fee, readonly=True).grid(row=7, column=1, sticky="w", pady=5)

        # Phí dịch vụ - NHẬP TAY (minibar, giặt ủi, ăn uống thêm...)
        self._field_label(frm, "Phí dịch vụ:").grid(row=8, column=0, sticky="e", pady=5, padx=(0, 8))
        self.var_service = tk.StringVar(value="0")
        self.entry_service = self._entry_style(frm, self.var_service, readonly=False)
        self.entry_service.grid(row=8, column=1, sticky="w", pady=5)
        self.entry_service.bind("<KeyRelease>", lambda e: self.recalc_total())

        # Tổng tiền (tự tính, luôn tính lại theo giá phòng hiện tại nếu còn Unpaid)
        self._field_label(frm, "Tổng tiền:").grid(row=9, column=0, sticky="e", pady=5, padx=(0, 8))
        self.var_total = tk.StringVar(value="0")
        self.entry_total = tk.Entry(
            frm, textvariable=self.var_total, width=40, state="readonly",
            font=(FONT_FAMILY, 11, "bold"), fg=COLOR_PRIMARY, bg=COLOR_CARD,
            relief="flat", highlightthickness=1, highlightbackground=COLOR_BORDER,
            highlightcolor=COLOR_SECONDARY, readonlybackground=COLOR_ENTRY_READONLY,
        )
        self.entry_total.grid(row=9, column=1, sticky="w", pady=5)

        # Trạng thái
        self._field_label(frm, "Trạng thái:").grid(row=10, column=0, sticky="e", pady=5, padx=(0, 8))
        self.cbo_status = ttk.Combobox(frm, values=list(STATUS_LABELS_VI.values()),
                                        state="readonly", width=36, font=FONT_BODY)
        self.cbo_status.set(STATUS_LABELS_VI["Unpaid"])
        self.cbo_status.grid(row=10, column=1, sticky="w", pady=5)

        # Thanh toán
        self._field_label(frm, "Thanh toán:").grid(row=11, column=0, sticky="e", pady=5, padx=(0, 8))
        self.cbo_payment = ttk.Combobox(frm, values=list(PAYMENT_LABELS_VI.values()),
                                         state="readonly", width=36, font=FONT_BODY)
        self.cbo_payment.set(PAYMENT_LABELS_VI["Cash"])
        self.cbo_payment.grid(row=11, column=1, sticky="w", pady=5)

        # Nút chức năng
        btn_frm = tk.Frame(frm, bg=COLOR_CARD)
        btn_frm.grid(row=12, column=0, columnspan=2, pady=(14, 4))
        ttk.Button(btn_frm, text="Tạo hóa đơn", style="Create.TButton",
                   command=self.on_create).pack(side="left", padx=5)
        self.btn_update = ttk.Button(btn_frm, text="Cập nhật", style="Update.TButton",
                                      command=self.on_update)
        self.btn_update.pack(side="left", padx=5)
        ttk.Button(btn_frm, text="Xuất PDF", style="Export.TButton",
                   command=self.on_export).pack(side="left", padx=5)
        ttk.Button(btn_frm, text="Làm mới", style="Clear.TButton",
                   command=self.on_clear).pack(side="left", padx=5)

    # -------------------------------------------------------------
    # KHÓA / MỞ KHÓA FORM theo trạng thái hóa đơn
    # -------------------------------------------------------------
    def _apply_lock_state(self, locked):
        """locked=True khi hóa đơn đang xem đã 'Đã thanh toán' -> vô hiệu hóa sửa."""
        self.is_locked = locked
        if locked:
            self.lbl_lock_banner.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
            self.cbo_status.configure(state="disabled")
            self.cbo_payment.configure(state="disabled")
            self.entry_service.configure(state="disabled")
            self.btn_update.configure(style="UpdateDisabled.TButton")
        else:
            self.lbl_lock_banner.grid_forget()
            self.cbo_status.configure(state="readonly")
            self.cbo_payment.configure(state="readonly")
            self.entry_service.configure(state="normal")
            self.btn_update.configure(style="Update.TButton")

    # -------------------------------------------------------------
    # BẢNG DANH SÁCH (phần dưới)
    # -------------------------------------------------------------
    def _build_table(self):
        outer = tk.Frame(self, bg=COLOR_BG)
        outer.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        table_frm = self._labelframe(outer, "Danh sách hóa đơn")
        table_frm.pack(fill="both", expand=True)

        filter_frm = tk.Frame(table_frm, bg=COLOR_CARD)
        filter_frm.pack(fill="x", pady=(0, 8))
        self._field_label(filter_frm, "Trạng thái:").pack(side="left")
        self.cbo_filter_status = ttk.Combobox(
            filter_frm, values=["Tất cả"] + list(STATUS_LABELS_VI.values()),
            state="readonly", width=16, font=FONT_BODY)
        self.cbo_filter_status.set("Tất cả")
        self.cbo_filter_status.pack(side="left", padx=8)
        ttk.Button(filter_frm, text="Lọc", style="Filter.TButton",
                   command=self.refresh_table).pack(side="left", padx=5)

        columns = ("id", "booking", "customer", "room", "amount", "status", "payment", "created_at")
        self.tree = ttk.Treeview(table_frm, columns=columns, show="headings", height=10)
        headers = ["Mã HĐ", "Đặt phòng", "Khách hàng", "Phòng", "Số tiền",
                   "Trạng thái", "Thanh toán", "Ngày tạo"]
        widths = [50, 70, 130, 80, 100, 110, 100, 140]
        for col, head, w in zip(columns, headers, widths):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=w, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_selected)

        self.tree.tag_configure("oddrow", background=COLOR_ROW_ALT)
        self.tree.tag_configure("evenrow", background=COLOR_CARD)
        for status, color in STATUS_COLORS.items():
            self.tree.tag_configure(status, foreground=color, font=(FONT_FAMILY, 10, "bold"))

    # -------------------------------------------------------------
    # NẠP DỮ LIỆU
    # -------------------------------------------------------------
    def refresh_bookings(self):
        self.bookings_cache.clear()
        rows = inv_srv.get_bookings_without_invoice()
        labels = []
        for r in rows:
            label = f"{r['booking_id']:03d} - {r['customer_name']} - Phòng {r['room_number']}"
            self.bookings_cache[label] = r
            labels.append(label)
        self.cbo_booking["values"] = labels

    def refresh_table(self):
        status_label = self.cbo_filter_status.get() if hasattr(self, "cbo_filter_status") else "Tất cả"
        status_code = STATUS_LABELS_VI_REV.get(status_label, "All") if status_label != "Tất cả" else "All"
        rows = inv_srv.get_invoices(status_filter=status_code)  # amount đã được tính "sống" nếu còn Unpaid
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, r in enumerate(rows):
            stripe = "evenrow" if i % 2 == 0 else "oddrow"
            self.tree.insert("", "end", tags=(stripe, r["status"]), values=(
                r["id"], r["booking_id"], r["customer_name"], r["room_number"],
                f"{float(r['amount']):,.0f}",
                STATUS_LABELS_VI.get(r["status"], r["status"]),
                PAYMENT_LABELS_VI.get(r["payment_method"], r["payment_method"]),
                r["created_at"]
            ))

    # -------------------------------------------------------------
    # SỰ KIỆN
    # -------------------------------------------------------------
    def on_booking_selected(self, event=None):
        label = self.cbo_booking.get()
        b = self.bookings_cache.get(label)
        if not b:
            return
        self.var_customer.set(b["customer_name"])
        self.var_room.set(f"{b['room_number']} - {b['room_type']}")
        self.var_checkin.set(str(b["checkin_date"]))
        self.var_checkout.set(str(b["checkout_date"]))
        self.var_price.set(str(b["price"]))
        self.var_late_fee.set(str(b.get("late_fee") or 0))
        self.var_service.set("0")  # hóa đơn mới -> phí dịch vụ mặc định 0, nhân viên tự nhập
        self.recalc_total()

    def recalc_total(self):
        label = self.cbo_booking.get()
        b = self.bookings_cache.get(label)
        if not b:
            return
        late_fee = float(b.get("late_fee") or 0)
        try:
            service_fee = float(self.var_service.get() or 0)
        except ValueError:
            service_fee = 0
        nights = inv_srv.calc_nights(b["checkin_date"], b["checkout_date"])
        total = inv_srv.calc_total(b["price"], nights, late_fee, service_fee)
        self.var_total.set(f"{total:,.0f}")

    def on_create(self):
        label = self.cbo_booking.get()
        b = self.bookings_cache.get(label)
        if not b:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một đặt phòng trước.")
            return
        try:
            total = float(self.var_total.get().replace(",", ""))
            service_fee = float(self.var_service.get() or 0)
            status_code = STATUS_LABELS_VI_REV.get(self.cbo_status.get(), "Unpaid")
            payment_code = PAYMENT_LABELS_VI_REV.get(self.cbo_payment.get(), "Cash")
            new_id = inv_srv.create_invoice(
                booking_id=b["booking_id"],
                amount=total,
                payment_method=payment_code,
                status=status_code,
                service_fee=service_fee,
            )
            messagebox.showinfo("Thành công", f"Đã tạo hóa đơn #{new_id}.")
            self.on_clear()
            self.refresh_bookings()
            self.refresh_table()
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def on_update(self):
        if self.is_locked:
            messagebox.showwarning(
                "Không thể sửa",
                "Hóa đơn này đã Đã thanh toán nên không thể chỉnh sửa nữa."
            )
            return
        if not self.current_invoice_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một hóa đơn trong danh sách trước.")
            return
        try:
            total = float(self.var_total.get().replace(",", ""))
            service_fee = float(self.var_service.get() or 0)
            status_code = STATUS_LABELS_VI_REV.get(self.cbo_status.get(), "Unpaid")
            payment_code = PAYMENT_LABELS_VI_REV.get(self.cbo_payment.get(), "Cash")
            # amount = tổng tiền ĐANG hiển thị (đã tính theo giá phòng hiện tại) ->
            # nếu status_code là 'Paid', số này sẽ được chốt cứng vĩnh viễn từ đây.
            inv_srv.update_invoice(
                self.current_invoice_id,
                amount=total,
                status=status_code,
                payment_method=payment_code,
                service_fee=service_fee,
            )
            messagebox.showinfo("Thành công", "Đã cập nhật hóa đơn.")
            self.refresh_table()
            # Tải lại để phản ánh đúng trạng thái khóa mới nhất
            inv = inv_srv.get_invoice_full(self.current_invoice_id)
            if inv:
                self._apply_lock_state(inv["status"] == "Paid")
        except inv_srv.InvoiceLockedError as e:
            messagebox.showwarning("Không thể sửa", str(e))
            self._apply_lock_state(True)
            self.refresh_table()
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def on_export(self):
        if not self.current_invoice_id:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một hóa đơn trong danh sách trước.")
            return
        try:
            path = inv_srv.export_invoice_pdf(self.current_invoice_id)
            messagebox.showinfo("Thành công", f"Đã xuất file: {path}")
        except Exception as e:
            messagebox.showerror("Lỗi", str(e))

    def on_clear(self):
        self.current_invoice_id = None
        self.cbo_booking.set("")
        self.var_customer.set("")
        self.var_room.set("")
        self.var_checkin.set("")
        self.var_checkout.set("")
        self.var_price.set("0")
        self.var_late_fee.set("0")
        self.var_service.set("0")
        self.var_total.set("0")
        self.cbo_status.set(STATUS_LABELS_VI["Unpaid"])
        self.cbo_payment.set(PAYMENT_LABELS_VI["Cash"])
        self._apply_lock_state(False)

    def on_row_selected(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        self.current_invoice_id = int(values[0])
        # Điền lại form từ dữ liệu đầy đủ + MỚI NHẤT trong DB (amount đã tính sống nếu Unpaid)
        inv = inv_srv.get_invoice_full(self.current_invoice_id)
        if not inv:
            return
        self.var_customer.set(inv["customer_name"])
        self.var_room.set(f"{inv['room_number']} - {inv['room_type']}")
        self.var_checkin.set(str(inv["checkin_date"]))
        self.var_checkout.set(str(inv["checkout_date"]))
        self.var_price.set(str(inv["price"]))
        self.var_late_fee.set(str(inv.get("late_fee") or 0))
        self.var_service.set(str(inv.get("service_fee") or 0))
        self.var_total.set(f"{float(inv['amount']):,.0f}")
        self.cbo_status.set(STATUS_LABELS_VI.get(inv["status"], inv["status"]))
        self.cbo_payment.set(PAYMENT_LABELS_VI.get(inv["payment_method"], inv["payment_method"]))
        self._apply_lock_state(inv["status"] == "Paid")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Hóa đơn")
    root.geometry("650x800")
    root.configure(bg=COLOR_BG)
    InvoiceFrame(root).pack(fill="both", expand=True)
    root.mainloop()
