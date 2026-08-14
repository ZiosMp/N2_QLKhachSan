"""
invoice_service.py
Các hàm nghiệp vụ cho module Invoices (Hóa đơn / Thanh toán)

Bảng invoices (theo hotel_management.sql + migrate_add_service_fee.sql):
    id, booking_id, amount, service_fee, created_at,
    status(Unpaid/Paid/Cancelled), payment_method(Cash/BankTransfer)

QUY TẮC QUAN TRỌNG:
- Khi hóa đơn còn "Unpaid": Tổng tiền KHÔNG lấy từ cột amount đã lưu, mà luôn
  tính lại "sống" (live) theo giá phòng HIỆN TẠI của booking (r.price) + phí
  quá giờ hiện tại (b.extra_fee) + phí dịch vụ (i.service_fee). Nhờ vậy nếu
  bên Booking đổi phòng (đổi room_id -> giá khác), hóa đơn tự cập nhật theo,
  không cần đồng bộ thủ công.
- Khi hóa đơn đã "Paid" hoặc "Cancelled": dùng đúng số tiền đã lưu cứng trong
  cột amount tại thời điểm chuyển trạng thái - KHÔNG tính lại nữa (chốt sổ).
- update_invoice() sẽ TỪ CHỐI mọi thay đổi nếu hóa đơn hiện đang ở trạng thái
  "Paid" - hóa đơn đã thanh toán thì không thể sửa lại dưới bất kỳ hình thức
  nào (kể cả gọi thẳng hàm này, không chỉ chặn ở giao diện).
"""
import sys
import os

BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from db import get_connection


# Biểu thức SQL dùng chung: tính lại tổng tiền "sống" theo giá phòng hiện tại.
# GREATEST(DATEDIFF(...), 1) tương đương calc_nights() bên Python (tối thiểu 1 đêm).
_LIVE_AMOUNT_SQL = """
    (r.price * GREATEST(DATEDIFF(b.checkout_date, b.checkin_date), 1)
     + IFNULL(b.extra_fee, 0) + IFNULL(i.service_fee, 0))
"""

# Khi hóa đơn đã Paid/Cancelled thì dùng số đã chốt (i.amount), không tính lại.
_RESOLVED_AMOUNT_SQL = f"""
    (CASE WHEN i.status = 'Unpaid' THEN {_LIVE_AMOUNT_SQL} ELSE i.amount END)
"""


# ---------------------------------------------------------------------
# 1. Lấy danh sách booking CHƯA có hóa đơn -> đổ vào combobox "Booking"
# ---------------------------------------------------------------------
def get_bookings_without_invoice():
    """
    Trả về list dict: id, customer_name, room_number, room_type,
    checkin_date, checkout_date, price
    Chỉ lấy các booking có status CheckedIn hoặc CheckedOut và chưa có invoice.
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    sql = """
        SELECT b.id AS booking_id, c.name AS customer_name,
               r.room_number, r.room_type, r.price,
               b.checkin_date, b.checkout_date,
               b.actual_checkin, b.actual_checkout, b.status,
               b.extended_hours, b.extra_fee AS late_fee
        FROM bookings b
        JOIN customers c ON b.customer_id = c.id
        JOIN rooms r ON b.room_id = r.id
        LEFT JOIN invoices i ON i.booking_id = b.id
        WHERE i.id IS NULL
          AND b.status IN ('CheckedIn', 'CheckedOut')
        ORDER BY b.id DESC
    """
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_booking_detail(booking_id):
    """Lấy chi tiết 1 booking để tự động điền Customer/Room/Check in/out/Price."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    sql = """
        SELECT b.id AS booking_id, c.name AS customer_name,
               r.room_number, r.room_type, r.price,
               b.checkin_date, b.checkout_date,
               b.extended_hours, b.extra_fee AS late_fee
        FROM bookings b
        JOIN customers c ON b.customer_id = c.id
        JOIN rooms r ON b.room_id = r.id
        WHERE b.id = %s
    """
    cur.execute(sql, (booking_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def calc_nights(checkin_date, checkout_date):
    """Số đêm ở = checkout - checkin (tối thiểu 1 đêm)."""
    nights = (checkout_date - checkin_date).days
    return max(nights, 1)


def calc_total(room_price, nights, late_fee, service_fee=0):
    """Tổng tiền = đơn giá phòng x số đêm + phí quá giờ + phí dịch vụ."""
    return float(room_price) * nights + float(late_fee) + float(service_fee)


def get_invoice_status(invoice_id):
    """Lấy nhanh trạng thái hiện tại của 1 hóa đơn (dùng để kiểm tra khóa)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM invoices WHERE id = %s", (invoice_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


# ---------------------------------------------------------------------
# 2. CREATE - Tạo hóa đơn mới (nút "Tạo hóa đơn")
# ---------------------------------------------------------------------
def create_invoice(booking_id, amount, payment_method, status="Unpaid", service_fee=0):
    """
    Thêm 1 hóa đơn mới cho booking.
    Lưu ý: amount truyền vào chỉ có ý nghĩa "chốt cứng" nếu status="Paid" ngay
    lúc tạo; nếu tạo với status="Unpaid" thì amount hiển thị ở các lần đọc sau
    vẫn sẽ được tính lại sống theo _RESOLVED_AMOUNT_SQL, không phụ thuộc giá
    trị lưu ở đây.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        sql = """
            INSERT INTO invoices (booking_id, amount, service_fee, status, payment_method)
            VALUES (%s, %s, %s, %s, %s)
        """
        cur.execute(sql, (booking_id, amount, service_fee, status, payment_method))
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------
# 3. UPDATE - Cập nhật hóa đơn (nút "Cập nhật")
#    - Chặn cứng: nếu hóa đơn đang ở trạng thái "Paid" thì KHÔNG cho sửa nữa.
#    - Khi đổi status sang "Paid": amount truyền vào (đã tính theo giá phòng
#      hiện tại ngay tại thời điểm bấm Cập nhật) sẽ được chốt cứng vào DB.
# ---------------------------------------------------------------------
class InvoiceLockedError(Exception):
    """Hóa đơn đã Paid, không được phép sửa nữa."""
    pass


def update_invoice(invoice_id, amount=None, status=None, payment_method=None, service_fee=None):
    current_status = get_invoice_status(invoice_id)
    if current_status is None:
        raise ValueError("Không tìm thấy hóa đơn.")
    if current_status == "Paid":
        raise InvoiceLockedError(
            "Hóa đơn này đã ở trạng thái Đã thanh toán nên không thể chỉnh sửa nữa."
        )

    fields, values = [], []
    if amount is not None:
        fields.append("amount = %s")
        values.append(amount)
    if service_fee is not None:
        fields.append("service_fee = %s")
        values.append(service_fee)
    if status is not None:
        fields.append("status = %s")
        values.append(status)
    if payment_method is not None:
        fields.append("payment_method = %s")
        values.append(payment_method)

    if not fields:
        return  # không có gì để update

    values.append(invoice_id)
    conn = get_connection()
    cur = conn.cursor()
    try:
        sql = f"UPDATE invoices SET {', '.join(fields)} WHERE id = %s"
        cur.execute(sql, values)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()


def mark_as_paid(invoice_id, payment_method, amount):
    """
    Tiện ích chốt thanh toán: LUÔN truyền amount = tổng tiền đang hiển thị
    (đã tính theo giá phòng hiện tại) để chốt cứng đúng số tại thời điểm này.
    """
    update_invoice(invoice_id, amount=amount, status="Paid", payment_method=payment_method)


def cancel_invoice(invoice_id):
    update_invoice(invoice_id, status="Cancelled")


# ---------------------------------------------------------------------
# 4. READ - Lấy danh sách hóa đơn cho bảng (Treeview) phía dưới form
# ---------------------------------------------------------------------
def get_invoices(status_filter=None, payment_filter=None):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    sql = f"""
        SELECT i.id, i.booking_id, c.name AS customer_name,
               r.room_number, {_RESOLVED_AMOUNT_SQL} AS amount,
               i.service_fee, i.status, i.payment_method, i.created_at
        FROM invoices i
        JOIN bookings b ON i.booking_id = b.id
        JOIN customers c ON b.customer_id = c.id
        JOIN rooms r ON b.room_id = r.id
        WHERE 1=1
    """
    params = []
    if status_filter and status_filter != "All":
        sql += " AND i.status = %s"
        params.append(status_filter)
    if payment_filter and payment_filter != "All":
        sql += " AND i.payment_method = %s"
        params.append(payment_filter)
    sql += " ORDER BY i.id DESC"

    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_invoice_full(invoice_id):
    """
    Lấy đầy đủ thông tin hóa đơn (dùng để hiển thị form / xuất PDF).
    'amount' trả về đã được tính đúng: sống theo giá phòng hiện tại nếu còn
    Unpaid, hoặc số đã chốt cứng nếu đã Paid/Cancelled.
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    sql = f"""
        SELECT i.id, i.booking_id, {_RESOLVED_AMOUNT_SQL} AS amount,
               i.service_fee, i.status, i.payment_method,
               i.created_at, c.name AS customer_name, c.phone, c.email,
               r.room_number, r.room_type, r.price,
               b.checkin_date, b.checkout_date,
               b.extended_hours, b.extra_fee AS late_fee
        FROM invoices i
        JOIN bookings b ON i.booking_id = b.id
        JOIN customers c ON b.customer_id = c.id
        JOIN rooms r ON b.room_id = r.id
        WHERE i.id = %s
    """
    cur.execute(sql, (invoice_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


# ---------------------------------------------------------------------
# 5. EXPORT - Xuất hóa đơn ra PDF (nút "Xuất PDF")
# ---------------------------------------------------------------------
def export_invoice_pdf(invoice_id, output_path=None):
    """
    Xuất 1 hóa đơn thành file PDF đẹp.
    Cần cài: pip install reportlab
    """
    from reportlab.lib.pagesizes import A5
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    inv = get_invoice_full(invoice_id)
    if not inv:
        raise ValueError("Không tìm thấy hóa đơn")

    if output_path is None:
        output_path = f"invoice_{invoice_id}.pdf"

    c = canvas.Canvas(output_path, pagesize=A5)
    width, height = A5
    y = height - 20 * mm

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y, "HOTEL INVOICE")
    y -= 12 * mm

    c.setFont("Helvetica", 10)
    lines = [
        f"Invoice ID       : {inv['id']}",
        f"Booking ID       : {inv['booking_id']}",
        f"Customer         : {inv['customer_name']}",
        f"Phone            : {inv['phone'] or '-'}",
        f"Room             : {inv['room_number']} ({inv['room_type']})",
        f"Check-in         : {inv['checkin_date']}",
        f"Check-out        : {inv['checkout_date']}",
        f"Room price/night : {inv['price']:,.0f}",
        f"Extended hours   : {inv.get('extended_hours') or 0}",
        f"Late fee         : {float(inv.get('late_fee') or 0):,.0f}",
        f"Service fee      : {float(inv.get('service_fee') or 0):,.0f}",
        "-" * 40,
        f"Total amount     : {float(inv['amount']):,.0f}",
        f"Status           : {inv['status']}",
        f"Payment method   : {inv['payment_method']}",
        f"Created at       : {inv['created_at']}",
    ]
    for line in lines:
        c.drawString(15 * mm, y, line)
        y -= 7 * mm

    c.save()
    return output_path
