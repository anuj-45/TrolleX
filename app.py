from flask import Flask, render_template, request, jsonify, send_file
import io
import qrcode

import core_smart_trolley as core

app = Flask(__name__)

# ---------- PAGES ----------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/payment")
def payment_page():
    return render_template("payment.html")


@app.route("/security")
def security_page():
    return render_template("security.html")


# ---------- API ENDPOINTS ----------

@app.route("/api/cart", methods=["GET"])
def api_cart():
    return jsonify({
        "items": core.cart_as_list(),
        "total": core.cart_total()
    })

@app.route("/api/remove-one", methods=["POST"])
def api_remove_one():
    data = request.get_json(silent=True) or {}
    barcode = data.get("barcode", "").strip()
    result = core.remove_one_weighted(barcode)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route("/api/scan", methods=["POST"])
def api_scan():
    data = request.get_json(silent=True) or {}
    barcode = data.get("barcode", "").strip()

    if not barcode:
        return jsonify({"ok": False, "error": "NO_BARCODE"}), 400

    result = core.add_to_cart(barcode)
    return jsonify(result)


@app.route("/api/start-payment", methods=["POST"])
def api_start_payment():
    result = core.start_payment()
    return jsonify(result)


@app.route("/api/payment-done", methods=["POST"])
def api_payment_done():
    result = core.mark_customer_paid()
    return jsonify(result)


@app.route("/api/security-check", methods=["POST"])
def api_security_check():
    data = request.get_json(silent=True) or {}
    passkey = data.get("passkey", "")
    confirm = bool(data.get("confirm", False))

    result = core.security_verify(passkey, confirm)
    return jsonify(result)


@app.route("/api/payment-qr")
def api_payment_qr():
    """Generate QR image for current payment UPI link."""
    info = core.start_payment()
    if not info.get("ok"):
        return jsonify(info), 400

    upi_link = info["upi_link"]

    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(upi_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


if __name__ == "__main__":
    ok = core.init_arduino("COM3", 57600)
    print("Arduino connected:", ok)
    app.run(host="0.0.0.0", port=5000, debug=True)
