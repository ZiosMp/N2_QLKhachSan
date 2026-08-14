CREATE DATABASE IF NOT EXISTS ql_khachsan;
USE ql_khachsan;


-- Bảng Rooms
CREATE TABLE IF NOT EXISTS rooms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    room_number VARCHAR(10) NOT NULL UNIQUE,
    room_type ENUM('Standard','Deluxe','Suite') NOT NULL,
    status ENUM('Empty','Booked','Occupied','Deactivated') DEFAULT 'Empty',
    price DECIMAL(10,2) NOT NULL,
    image_url VARCHAR(255)
);

-- Bảng Customers
CREATE TABLE IF NOT EXISTS customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    address VARCHAR(255),
    id_type ENUM('CCCD','Passport') DEFAULT 'CCCD',
    id_number VARCHAR(20) UNIQUE
);

-- Bảng Bookings
CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    room_id INT NOT NULL,
    checkin_date DATE NOT NULL,
    checkout_date DATE NOT NULL,
    actual_checkin DATETIME,
    actual_checkout DATETIME,
    status ENUM('Booked','Cancelled','CheckedIn','CheckedOut') DEFAULT 'Booked',
    booking_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    extended_hours INT DEFAULT 0,
    extra_fee DECIMAL(10,2) DEFAULT 0.00,
    room_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    room_number VARCHAR(10) NOT NULL DEFAULT '',
    room_type ENUM('Standard','Deluxe','Suite') NOT NULL DEFAULT 'Standard',
    room_image_url VARCHAR(255),
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (room_id) REFERENCES rooms(id)
);

-- Bảng Invoices
CREATE TABLE IF NOT EXISTS invoices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('Paid','Unpaid','Cancelled') DEFAULT 'Unpaid',
    payment_method ENUM('Cash','BankTransfer') DEFAULT 'Cash',
    FOREIGN KEY (booking_id) REFERENCES bookings(id)
);
-- Bảng dịch vụ
CREATE TABLE IF NOT EXISTS supplies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    unit VARCHAR(20) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    quantity INT DEFAULT 0
);
-- Bảng chi tiết dịch vụ sử dụng trong booking

CREATE TABLE IF NOT EXISTS booking_supplies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    supply_id INT NOT NULL,
    quantity INT NOT NULL,
    used_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (booking_id) REFERENCES bookings(id),
    FOREIGN KEY (supply_id) REFERENCES supplies(id)
);
CREATE TABLE IF NOT EXISTS consultation_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    room_id INT NOT NULL,
    full_name VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(100),
    note VARCHAR(255),
    status ENUM('New','Contacted','Closed') DEFAULT 'New',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_id) REFERENCES rooms(id)
);
USE ql_khachsan;

ALTER TABLE bookings
    ADD COLUMN room_number VARCHAR(10) NOT NULL DEFAULT '' AFTER room_price,
    ADD COLUMN room_type ENUM('Standard','Deluxe','Suite') NOT NULL DEFAULT 'Standard' AFTER room_number,
    ADD COLUMN room_image_url VARCHAR(255) AFTER room_type;

SET SQL_SAFE_UPDATES = 0;

UPDATE bookings b
JOIN rooms r ON b.room_id = r.id
SET b.room_number = r.room_number,
    b.room_type = r.room_type,
    b.room_image_url = r.image_url
WHERE b.room_number = '';

SET SQL_SAFE_UPDATES = 1;




