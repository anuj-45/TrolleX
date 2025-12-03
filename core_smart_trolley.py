import time
import serial

# ---------- ARDUINO / LOAD CELL SETTINGS ----------

arduino = None
arduino_connected = False  # flag


def init_arduino(port="COM3", baudrate=57600):
    """Try to connect to Arduino. Returns True if OK, False otherwise."""
    global arduino, arduino_connected
    try:
        arduino = serial.Serial(port, baudrate)
        time.sleep(2)
        arduino_connected = True
    except Exception:
        arduino = None
        arduino_connected = False
    return arduino_connected


MARGIN = 20  # grams tolerance

PRODUCT_WEIGHTS = {
    "8901030862243": 60,   # Vim Bar
    "8901248701129": 18,   # Zandu Balm
    "8901248701129": 18,   # Zandu Balm
    "8901719134852": 91,   # Parle-G
    "8901399005169": 140,  # Santoor 150gm
    "000022": 500,         # Tur dal 500gm
    "8901399007811": 39,   # Santoor 40gm
}

PRODUCTS = {
    "8901030862243": ["Vim Bar", 10],
    "8901248701129": ["Zandu ultra power balm", 51],
    "8901719134852": ["Parle-G", 10],
    "8901399005169": ["Santoor 150gm", 67],
    "000022": ["Tur dal 500gm", 65],
    "8901399007811": ["Santoor 40gm", 10],
}

SECURITY_PASS = "1234"

# ---------- RUNTIME STATE ----------

cart = {}  # barcode -> [name, qty, price]

last_stable_weight = 0.0
monitor_enabled = True

payment_started = False
payment_done_by_customer = False


# ---------- WEIGHT / CART LOGIC ----------

def read_weight(timeout=2.5):
    """Read stable weight from Arduino; return last_stable_weight if unstable or no Arduino."""
    global last_stable_weight

    if not arduino_connected:
        # Arduino not connected: behave as if weight is stable at last_stable_weight
        return last_stable_weight

    arduino.reset_input_buffer()
    readings = []
    start_time = time.time()

    while time.time() - start_time < timeout:
        if arduino.in_waiting > 0:
            try:
                line = arduino.readline().decode().strip()
                if not line:
                    continue
                weight = float(line)
                readings.append(weight)
                if len(readings) > 3:
                    readings.pop(0)

                if len(readings) >= 2 and max(readings) - min(readings) <= 2:
                    stable = sum(readings) / len(readings)
                    if abs(stable) < 3:
                        stable = 0.0
                    return stable
            except ValueError:
                continue

    return last_stable_weight


def total_expected_weight():
    total = 0
    for code, (name, qty, price) in cart.items():
        if code in PRODUCT_WEIGHTS:
            total += PRODUCT_WEIGHTS[code] * qty
    return total


def verify_cart_weight():
    actual = read_weight()
    expected = total_expected_weight()
    diff = actual - expected

    if abs(diff) <= MARGIN:
        return {"ok": True, "message": "Weight OK", "actual": actual, "expected": expected}

    if diff > 0:
        status = "extra"
        message = "Extra item added without scanning."
    else:
        status = "missing"
        message = "Item removed without scanning."

    return {
        "ok": False,
        "status": status,
        "message": message,
        "actual": actual,
        "expected": expected,
    }


def add_to_cart(barcode):
    """Process one scanned barcode and return result dict for frontend."""
    global last_stable_weight

    if barcode not in PRODUCTS:
        return {"ok": False, "error": "UNKNOWN_BARCODE", "message": f"Barcode {barcode} not found."}

    name, price = PRODUCTS[barcode]
    expected_item_weight = PRODUCT_WEIGHTS.get(barcode, 0)

    if expected_item_weight == 0:
        return {"ok": False, "error": "NO_WEIGHT", "message": f"No expected weight for {barcode}."}

    # check if this item was already in cart
    old_qty = cart[barcode][1] if barcode in cart else 0
    double_scan = old_qty >= 1

    # baseline before placing
    weight_before = last_stable_weight

    # if Arduino is not connected, skip real weight logic and just add item
    if not arduino_connected:
        if barcode in cart:
            cart[barcode][1] += 1
        else:
            cart[barcode] = [name, 1, price]
        last_stable_weight += expected_item_weight
        total = cart_total()
        return {
            "ok": True,
            "name": name,
            "price": price,
            "qty": cart[barcode][1],
            "diff": 0.0,
            "expected_item_weight": expected_item_weight,
            "cart": cart_as_list(),
            "total": total,
            "double_scan": double_scan,
            "weight_check": {"ok": True, "message": "Arduino not connected; weight check skipped."},
        }

    # ----- real weight flow when Arduino is connected -----
    start_time = time.time()
    stable_candidates = []

    while time.time() - start_time < 6:
        w = read_weight()
        if w > weight_before + 5:
            stable_candidates.append(w)
        time.sleep(0.5)

    if stable_candidates:
        weight_after = max(stable_candidates)
    else:
        weight_after = weight_before

    diff = abs(weight_after - weight_before)

    if abs(diff - expected_item_weight) <= MARGIN:
        if barcode in cart:
            cart[barcode][1] += 1
        else:
            cart[barcode] = [name, 1, price]

        last_stable_weight += expected_item_weight

        total = cart_total()
        weight_check = verify_cart_weight()

        return {
            "ok": True,
            "name": name,
            "price": price,
            "qty": cart[barcode][1],
            "diff": diff,
            "expected_item_weight": expected_item_weight,
            "cart": cart_as_list(),
            "total": total,
            "double_scan": double_scan,
            "weight_check": weight_check,
        }

    return {
        "ok": False,
        "error": "WEIGHT_MISMATCH",
        "message": "Measured weight does not match expected item weight.",
        "diff": diff,
        "expected_item_weight": expected_item_weight,
    }

def remove_one_weighted(barcode):
    """Remove one quantity of an item with weight check."""
    global last_stable_weight

    if barcode not in cart:
        return {"ok": False, "error": "NOT_IN_CART", "message": "Item not in cart."}

    name, qty, price = cart[barcode]
    expected_item_weight = PRODUCT_WEIGHTS.get(barcode, 0)

    if expected_item_weight == 0:
        return {"ok": False, "error": "NO_WEIGHT", "message": f"No expected weight for {barcode}."}

    # If Arduino not connected, skip weight logic but still allow removal (for testing)
    if not arduino_connected:
        if qty > 1:
            cart[barcode][1] -= 1
        else:
            del cart[barcode]
        last_stable_weight = max(0.0, last_stable_weight - expected_item_weight)
        return {
            "ok": True,
            "message": f"Removed one {name} (Arduino not connected, weight check skipped).",
            "cart": cart_as_list(),
            "total": cart_total(),
        }

    # ---- real weight check ----
    weight_before = read_weight()

    # Ask frontend to tell customer: "Please remove the item now"
    # Then wait up to 6 seconds for stable lower weight
    start_time = time.time()
    candidates = []

    while time.time() - start_time < 6:
        w = read_weight()
        if w < weight_before - 5:  # significant drop
            candidates.append(w)
        time.sleep(0.5)

    if candidates:
        weight_after = min(candidates)
    else:
        weight_after = weight_before

    diff = abs(weight_before - weight_after)

    if abs(diff - expected_item_weight) <= MARGIN:
        # Accept removal
        if qty > 1:
            cart[barcode][1] -= 1
        else:
            del cart[barcode]

        last_stable_weight = max(0.0, last_stable_weight - expected_item_weight)

        return {
            "ok": True,
            "message": f"Removed one {name}.",
            "diff": diff,
            "expected_item_weight": expected_item_weight,
            "cart": cart_as_list(),
            "total": cart_total(),
        }

    return {
        "ok": False,
        "error": "WEIGHT_NOT_DROPPED",
        "message": "Weight did not drop as expected. Please check trolley.",
        "diff": diff,
        "expected_item_weight": expected_item_weight,
    }


def cart_as_list():
    """Return cart as a list of dicts for JSON."""
    items = []
    for code, (name, qty, price) in cart.items():
        items.append(
            {
                "barcode": code,
                "name": name,
                "qty": qty,
                "price": price,
                "line_total": price * qty,
            }
        )
    return items


def cart_total():
    return sum(price * qty for (name, qty, price) in cart.values())


# ---------- PAYMENT / SECURITY ----------

def start_payment():
    """Prepare payment info and return UPI link."""
    global payment_started, payment_done_by_customer

    total = cart_total()
    if total <= 0:
        return {"ok": False, "error": "EMPTY_CART", "message": "Cart is empty."}

    payment_started = True
    payment_done_by_customer = False

    upi_link = f"upi://pay?pa=9975068503@kotak&pn=Anuj&am={total}&cu=INR"

    return {
        "ok": True,
        "total": total,
        "upi_link": upi_link,
    }


def mark_customer_paid():
    """Customer presses 'Payment Done'."""
    global payment_done_by_customer
    payment_done_by_customer = True
    return {"ok": True}


def security_verify(passkey: str, confirm_payment: bool):
    """Security guard verifies payment with passkey and confirmation."""
    global cart, monitor_enabled, payment_started

    if not payment_started:
        return {"ok": False, "error": "NO_PAYMENT_PAGE", "message": "Payment not started."}

    if not cart:
        monitor_enabled = False
        return {"ok": True, "message": "Cart empty, session finished."}

    if not payment_done_by_customer:
        return {"ok": False, "error": "CUSTOMER_NOT_CONFIRMED", "message": "Customer has not confirmed payment yet."}

    if passkey != SECURITY_PASS:
        return {"ok": False, "error": "BAD_PASSKEY", "message": "Incorrect passkey."}

    if not confirm_payment:
        return {"ok": False, "error": "NOT_CONFIRMED", "message": "Security did not confirm payment."}

    cart.clear()
    monitor_enabled = False
    payment_started = False
    return {"ok": True, "message": "Payment verified, cart cleared."}
