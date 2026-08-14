"""
statistics_service.py
Các hàm nghiệp vụ cho module Thống kê (Reports)
Không có bảng riêng - dữ liệu được tổng hợp (aggregate) từ bookings + invoices.
"""
import sys
import os

BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from db import get_connection


# Biểu thức SQL dùng chung với invoice_service.py: hóa đơn còn Unpaid thì tính
# "sống" theo giá phòng hiện tại + phí quá giờ + phí dịch vụ; Paid/Cancelled
# thì dùng số đã chốt cứng trong i.amount.
_RESOLVED_AMOUNT_SQL = """
    (CASE WHEN i.status = 'Unpaid'
          THEN (r.price * GREATEST(DATEDIFF(b.checkout_date, b.checkin_date), 1)
                + IFNULL(b.extra_fee, 0) + IFNULL(i.service_fee, 0))
          ELSE i.amount END)
"""


# ---------------------------------------------------------------------
# 1. Thống kê tổng quan trong khoảng thời gian [start_date, end_date]
# ---------------------------------------------------------------------
def get_statistics(start_date, end_date):
    """
    Trả về dict gồm:
        total_revenue        : tổng doanh thu (chỉ tính hóa đơn Paid)
        total_unpaid          : tổng tiền chưa thu
        total_bookings        : số lượt đặt phòng
        total_customers       : số khách hàng khác nhau
        revenue_by_payment    : {'Cash': x, 'BankTransfer': y}
        revenue_by_room_type  : {'Standard': x, 'Deluxe': y, 'Suite': z}
    """
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    stats = {}

    # Tổng doanh thu đã thu (Paid) - số đã chốt cứng, không cần tính lại
    cur.execute("""
        SELECT COALESCE(SUM(i.amount), 0) AS total
        FROM invoices i
        WHERE i.status = 'Paid'
          AND DATE(i.created_at) BETWEEN %s AND %s
    """, (start_date, end_date))
    stats["total_revenue"] = float(cur.fetchone()["total"])

    # Tổng tiền chưa thu (Unpaid) - tính "sống" theo giá phòng HIỆN TẠI,
    # nên nếu Booking đổi phòng thì số này tự cập nhật theo.
    cur.execute(f"""
        SELECT COALESCE(SUM({_RESOLVED_AMOUNT_SQL}), 0) AS total
        FROM invoices i
        JOIN bookings b ON i.booking_id = b.id
        JOIN rooms r ON b.room_id = r.id
        WHERE i.status = 'Unpaid'
          AND DATE(i.created_at) BETWEEN %s AND %s
    """, (start_date, end_date))
    stats["total_unpaid"] = float(cur.fetchone()["total"])

    # Số lượt booking trong khoảng thời gian
    cur.execute("""
        SELECT COUNT(*) AS cnt FROM bookings
        WHERE DATE(booking_date) BETWEEN %s AND %s
    """, (start_date, end_date))
    stats["total_bookings"] = cur.fetchone()["cnt"]

    # Số khách hàng khác nhau đã đặt phòng trong khoảng thời gian
    cur.execute("""
        SELECT COUNT(DISTINCT customer_id) AS cnt FROM bookings
        WHERE DATE(booking_date) BETWEEN %s AND %s
    """, (start_date, end_date))
    stats["total_customers"] = cur.fetchone()["cnt"]

    # Doanh thu theo phương thức thanh toán
    cur.execute("""
        SELECT i.payment_method, COALESCE(SUM(i.amount), 0) AS total
        FROM invoices i
        WHERE i.status = 'Paid'
          AND DATE(i.created_at) BETWEEN %s AND %s
        GROUP BY i.payment_method
    """, (start_date, end_date))
    stats["revenue_by_payment"] = {r["payment_method"]: float(r["total"]) for r in cur.fetchall()}

    # Doanh thu theo loại phòng
    cur.execute("""
        SELECT r.room_type, COALESCE(SUM(i.amount), 0) AS total
        FROM invoices i
        JOIN bookings b ON i.booking_id = b.id
        JOIN rooms r ON b.room_id = r.id
        WHERE i.status = 'Paid'
          AND DATE(i.created_at) BETWEEN %s AND %s
        GROUP BY r.room_type
    """, (start_date, end_date))
    stats["revenue_by_room_type"] = {r["room_type"]: float(r["total"]) for r in cur.fetchall()}

    cur.close()
    conn.close()
    return stats


def get_invoice_rows(start_date, end_date):
    """Chi tiết từng hóa đơn trong khoảng thời gian, dùng để xuất báo cáo chi tiết."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(f"""
        SELECT i.id, i.booking_id, c.name AS customer_name, r.room_number,
               r.room_type, {_RESOLVED_AMOUNT_SQL} AS amount,
               i.status, i.payment_method, i.created_at
        FROM invoices i
        JOIN bookings b ON i.booking_id = b.id
        JOIN customers c ON b.customer_id = c.id
        JOIN rooms r ON b.room_id = r.id
        WHERE DATE(i.created_at) BETWEEN %s AND %s
        ORDER BY i.created_at
    """, (start_date, end_date))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


# ---------------------------------------------------------------------
# 2. Xuất báo cáo ra Excel
# ---------------------------------------------------------------------
def export_report_excel(start_date, end_date, output_path="report.xlsx"):
    """
    Cần cài: pip install openpyxl
    Tạo 2 sheet: "Summary" (tổng hợp) và "Details" (chi tiết từng hóa đơn)
    """
    from openpyxl import Workbook

    stats = get_statistics(start_date, end_date)
    rows = get_invoice_rows(start_date, end_date)

    wb = Workbook()

    # --- Sheet Summary ---
    ws1 = wb.active
    ws1.title = "Summary"
    ws1.append(["Hotel Revenue Report", "", ""])
    ws1.append(["From", str(start_date), "To", str(end_date)])
    ws1.append([])
    ws1.append(["Total revenue (Paid)", stats["total_revenue"]])
    ws1.append(["Total unpaid", stats["total_unpaid"]])
    ws1.append(["Total bookings", stats["total_bookings"]])
    ws1.append(["Total customers", stats["total_customers"]])
    ws1.append([])
    ws1.append(["Revenue by payment method"])
    for k, v in stats["revenue_by_payment"].items():
        ws1.append([k, v])
    ws1.append([])
    ws1.append(["Revenue by room type"])
    for k, v in stats["revenue_by_room_type"].items():
        ws1.append([k, v])

    # --- Sheet Details ---
    ws2 = wb.create_sheet("Details")
    ws2.append(["Invoice ID", "Booking ID", "Customer", "Room", "Room Type",
                "Amount", "Status", "Payment Method", "Created At"])
    for r in rows:
        ws2.append([r["id"], r["booking_id"], r["customer_name"], r["room_number"],
                    r["room_type"], float(r["amount"]), r["status"],
                    r["payment_method"], str(r["created_at"])])

    wb.save(output_path)
    return output_path
