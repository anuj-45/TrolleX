# core_smart_trolley.py - WiFi weight version
import time
import requests

# -------------------------------
# ESP32 + WEIGHT SETTINGS (WiFi)
# -------------------------------
ESP_IP = "172.17.42.125"  # your ESP32 IP

MARGIN = 20

# -------------------------------
# PRODUCT DATA (EXACT COPY)
# -------------------------------
PRODUCT_WEIGHTS = {
    "8901030862243": 60,    # Vim Bar
    "8901248701129": 18,    # Zandu Balm
    "8901719134852": 91,    # Parle-G
    "8901399005169": 140,   # Santoor 150gm
    "000022": 500,          # Tur dal 500gm
    "8901399007811": 39,    # Santoor 40gm
}

PRODUCTS = {
    "8901030862243": ["Vim Bar", 10],
    "8901248701129": ["Zandu ultra power balm", 51],
    "8901719134852": ["Parle-G", 10],
    "8901399005169": ["Santoor 150gm", 67],
    "000022": ["Tur dal 500gm", 65],
    "8901399007811": ["Santoor 40gm", 10],
}

# -------------------------------
# GLOBALS (EXACT)
# -------------------------------
cart = {}  # Dict format like Tkinter
last_stable_weight = 0.0
processing_scan = False
monitor_enabled = True


def read_weight():
    """WiFi version of read_weight(): gets stable weight from ESP32 /weight"""
    global last_stable_weight

    readings = []
    start_time = time.time()

    while time.time() - start_time < 2.5:
        try:
            r = requests.get(f"http://{ESP_IP}/weight", timeout=1)
            data = r.json()
            w = float(data.get("weight", 0))
        except Exception:
            # network or parse error, skip this sample
            continue

        readings.append(w)
        if len(readings) > 3:
            readings.pop(0)

        if len(readings) >= 2 and max(readings) - min(readings) <= 2:
            stable = sum(readings) / len(readings)
            if abs(stable) < 3:
                stable = 0.0
            print(f"[DEBUG] Stable weight: {stable:.2f} g")
            last_stable_weight = stable
            return stable

    print(f"[DEBUG] ❌ No stable weight found, using last stable: {last_stable_weight:.2f} g")
    return last_stable_weight


def total_expected_weight():
    """EXACT Tkinter total_expected_weight()"""
    total = 0
    for code, data in cart.items():
        name, qty, price = data
        if code in PRODUCT_WEIGHTS:
            total += PRODUCT_WEIGHTS[code] * qty
    return total


def add_to_cart(barcode):
    """EXACT Tkinter logic with monitoring pause"""
    global processing_scan, monitor_enabled, last_stable_weight

    if processing_scan:
        return {"ok": False, "error": "PROCESSING"}

    processing_scan = True
    monitor_enabled = False  # PAUSE MONITORING DURING SCAN

    try:
        print(f"[DEBUG] Scanned barcode: {barcode}")

        if barcode not in PRODUCTS:
            return {
                "ok": False,
                "error": "UNKNOWN_BARCODE",
                "message": f"Barcode {barcode} not found",
            }

        name, price = PRODUCTS[barcode]
        expected_item_weight = PRODUCT_WEIGHTS.get(barcode, 0)

        # Stable baseline (EXACT Tkinter)
        print("[DEBUG] Waiting for stable baseline...")
        stable_empty = False
        empty_start = time.time()
        while time.time() - empty_start < 6:
            w = read_weight()
            if 0 <= w <= 5 or abs(w - last_stable_weight) <= 3:
                stable_empty = True
                break
            time.sleep(0.5)

        if not stable_empty:
            weight_before = last_stable_weight
        else:
            weight_before = last_stable_weight
        print(f"[DEBUG] Weight before placing: {weight_before:.2f}g")

        # Wait for stable after placing (EXACT Tkinter)
        start_time = time.time()
        stable_after_values = []
        while time.time() - start_time < 6:
            w = read_weight()
            if w > weight_before + 5:
                stable_after_values.append(w)
            time.sleep(0.8)

        if stable_after_values:
            weight_after = max(stable_after_values)
        else:
            weight_after = weight_before

        print(f"[DEBUG] Weight after placing: {weight_after:.2f}g")
        diff = abs(weight_after - weight_before)
        print(f"[DEBUG] ΔWeight: {diff:.2f}g")

        if abs(diff - expected_item_weight) <= MARGIN:
            if barcode in cart:
                cart[barcode][1] += 1  # qty
            else:
                cart[barcode] = [name, 1, price]

            last_stable_weight += expected_item_weight
            total = sum(data[1] * data[2] for data in cart.values())

            print(f"[DEBUG] ✅ Added {name}, weight OK ({diff:.2f}g ≈ {expected_item_weight}g)")
            print(f"[DEBUG] Updated total stable trolley weight: {last_stable_weight:.2f}g")

            return {
                "ok": True,
                "message": f"{name} added successfully!",
                "barcode": barcode,
                "total": total,
            }
        else:
            return {
                "ok": False,
                "error": "WEIGHT_MISMATCH",
                "message": f"Measured: {diff:.1f}g (Expected: {expected_item_weight}g)",
            }
    finally:
        processing_scan = False
        monitor_enabled = True  # RESUME MONITORING
        print("[DEBUG] Monitoring resumed")


def remove_one_weighted(barcode):
    """COMPLETE remove with monitoring pause"""
    global monitor_enabled, last_stable_weight

    monitor_enabled = False  # PAUSE MONITORING

    try:
        if barcode not in cart or cart[barcode][1] <= 0:
            return {
                "ok": False,
                "error": "NOT_IN_CART",
                "message": "Item not in cart",
            }

        name, qty, price = cart[barcode]
        expected_weight = PRODUCT_WEIGHTS[barcode]

        # Weight before removal
        before = read_weight()
        print(f"[DEBUG] Weight before remove: {before:.2f}g")

        print("[DEBUG] Remove item and wait...")
        time.sleep(2.5)

        # Weight after removal
        after = read_weight()
        drop = abs(before - after)
        print(f"[DEBUG] Weight after remove: {after:.2f}g | Drop: {drop:.2f}g")

        if abs(drop - expected_weight) <= MARGIN:
            cart[barcode][1] -= 1
            if cart[barcode][1] == 0:
                del cart[barcode]
            last_stable_weight -= expected_weight
            total = sum(data[1] * data[2] for data in cart.values())

            print(f"[DEBUG] ✅ Removed {name}, drop OK ({drop:.2f}g ≈ {expected_weight}g)")
            print(f"[DEBUG] Updated total stable trolley weight: {last_stable_weight:.2f}g")

            return {
                "ok": True,
                "message": f"Removed {name}",
                "barcode": barcode,
                "total": total,
            }
        else:
            return {
                "ok": False,
                "error": "WEIGHT_NOT_DROPPED",
                "message": f"Drop: {drop:.1f}g (Expected: {expected_weight}g)",
            }
    finally:
        monitor_enabled = True  # RESUME MONITORING
        print("[DEBUG] Monitoring resumed")


def verify_cart_weight():
    """Only runs when NOT processing scan"""
    if not monitor_enabled:
        return {"ok": True, "skipped": "scan_active"}

    actual = read_weight()
    expected = total_expected_weight()

    if abs(actual - expected) > MARGIN:
        if actual > expected:
            return {"alert": "⚠️ Extra item added without scanning!"}
        elif actual < expected:
            return {"alert": "⚠️ Item removed without scanning!"}
    return {"ok": True}


def monitor_weight():
    """Background monitoring - runs every 2s like Tkinter"""
    result = verify_cart_weight()
    if "alert" in result:
        print(f"[SECURITY ALERT] {result['alert']}")
    return result


# API Functions (for app.py)
def cart_as_list():
    items = []
    for code, data in cart.items():
        name, qty, price = data
        items.append(
            {
                "barcode": code,
                "name": name,
                "qty": qty,
                "price": price,
            }
        )
    return items


def cart_total():
    return sum(data[1] * data[2] for data in cart.values())


def clear_cart():
    global cart, last_stable_weight
    cart.clear()
    last_stable_weight = 0.0
    return True


def finish_shopping():
    """Generate QR payment + total (Tkinter finish_shopping)"""
    total = cart_total()
    if total == 0:
        return {"ok": False, "error": "CART_EMPTY"}

    upi_link = f"upi://pay?pa=9975068503@kotak&pn=Anuj&am={total}&cu=INR"

    return {
        "ok": True,
        "total": total,
        "upi_link": upi_link,
        "items": cart_as_list(),
        "message": "Scan QR to pay",
    }


def customer_done():
    """Customer confirms payment"""
    return {"payment_confirmed": True}


def security_check(passkey):
    """Security passkey check (Tkinter SECURITY_PASS = "1234")"""
    if passkey == "1234":
        clear_cart()
        return {"ok": True, "message": "Payment verified. Cart cleared!"}
    return {"ok": False, "error": "WRONG_PASSKEY"}
