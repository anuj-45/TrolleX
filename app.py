from flask import Flask, render_template, request, jsonify, send_file
import io
import qrcode
import core_smart_trolley as core

app = Flask(__name__)

# ----------------- WEIGHT STORAGE (for ESP32) -----------------
current_weight = 0.0  # latest weight sent from ESP32


@app.route("/api/update_weight", methods=["POST"])
def update_weight():
    """
    ESP32 calls this endpoint (HTTP POST) with JSON: {"weight": <value>}
    to update the latest weight on the server.
    """
    global current_weight
    data = request.get_json(force=True) or {}
    try:
        current_weight = float(data.get("weight", 0))
    except (TypeError, ValueError):
        current_weight = 0.0
    return jsonify({"ok": True})


@app.route("/api/get_weight", methods=["GET"])
def get_weight():
    """
    Frontend/app can call this to read latest weight stored on server.
    """
    return jsonify({"weight": current_weight})


# ---------- PAGES ----------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/payment")
def payment_page():
    total = request.args.get('total', 0)
    upi = request.args.get('upi', '')
    return render_template("payment.html", total=total, upi_link=upi)


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
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route('/api/monitor', methods=['GET'])
def api_monitor():
    result = core.verify_cart_weight()
    return jsonify(result)


@app.route("/api/finish-shopping", methods=["POST"])
def api_finish_shopping():
    result = core.finish_shopping()
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route("/api/payment-done", methods=["POST"])
def api_payment_done():
    result = core.customer_done()
    return jsonify(result)


@app.route("/api/security-check", methods=["POST"])
def api_security_check():
    data = request.get_json(silent=True) or {}
    passkey = data.get("passkey", "")
    result = core.security_check(passkey)
    return jsonify(result)


@app.route("/api/payment-qr")
def api_payment_qr():
    info = core.finish_shopping()
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
    # Local dev run
    app.run(host="0.0.0.0", port=5000, debug=False)
