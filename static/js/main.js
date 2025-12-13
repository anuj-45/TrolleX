// ---- Backend base URL ----
// For local testing:
// const BASE_URL = "http://localhost:5000";

// After deploy to Render:
const BASE_URL = "https://YOUR-RENDER-NAME.onrender.com";


// ---- Cart state held on frontend for duplicate check ----

let lastCart = [];

function itemInCart(barcode) {
  return lastCart.find(it => it.barcode === barcode);
}


// ---- Load cart from backend and render ----

async function fetchCart() {
  const res = await fetch(`${BASE_URL}/api/cart`);
  const data = await res.json();

  lastCart = data.items || [];

  const tbody = document.getElementById("cart-body");
  const totalEl = document.getElementById("total-amount");
  if (!tbody || !totalEl) return;

  tbody.innerHTML = "";
  lastCart.forEach(item => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.barcode}</td>
      <td>${item.name}</td>
      <td>${item.price}</td>
      <td>${item.qty}</td>
      <td>${item.line_total}</td>
      <td>
        <button class="remove-btn" data-barcode="${item.barcode}" data-name="${item.name}">
          Remove 1
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll(".remove-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const bc = btn.dataset.barcode;
      const name = btn.dataset.name;
      removeOneWithConfirm(bc, name);
    });
  });

  totalEl.textContent = "₹" + (data.total || 0);
}


// ---- Scan / add item ----

async function scanBarcode() {
  const input = document.getElementById("barcode-input");
  const status = document.getElementById("status-text");
  const barcode = (input.value || "").trim();
  if (!barcode) return;

  // If item already in cart, ask confirmation
  const existing = itemInCart(barcode);
  if (existing) {
    const ok = window.confirm(
      `Do you want to add ${existing.name} again?`
    );
    if (!ok) {
      status.textContent = "Cancelled adding duplicate item.";
      status.className = "status warning";
      input.value = "";
      return;
    }
  }

  status.textContent = "Processing scan…";
  status.className = "status";

  const res = await fetch(`${BASE_URL}/api/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ barcode })
  });
  const data = await res.json();

  if (data.ok) {
    status.textContent = `Added: ${data.name}`;
    status.className = "status ok";
    input.value = "";
    fetchCart();
  } else {
    status.textContent = data.message || "Error while adding item.";
    status.className = "status error";
  }
}


// ---- Weighted Remove 1 with confirmation ----

async function removeOneWithConfirm(barcode, name) {
  const status = document.getElementById("status-text");

  const ok = window.confirm(`Do you want to remove 1 x ${name}?`);
  if (!ok) {
    status.textContent = "Remove cancelled.";
    status.className = "status warning";
    return;
  }

  status.textContent = "Please remove the item from trolley and wait…";
  status.className = "status";

  const res = await fetch(`${BASE_URL}/api/remove-one`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ barcode })
  });
  const data = await res.json();

  if (data.ok) {
    status.textContent = data.message || "Item removed.";
    status.className = "status ok";
    fetchCart();
  } else {
    status.textContent = data.message || "Cannot remove item.";
    status.className = "status error";
  }
}


// ---- Background weight security monitor ----

setInterval(() => {
  fetch(`${BASE_URL}/api/monitor`)
    .then(r => r.json())
    .then(data => {
      if (data.alert) {
        alert(data.alert);  // Popup like Tkinter
      }
    })
    .catch(err => console.error("Monitor error", err));
}, 2000);  // Every 2s like Tkinter root.after(2000)


// ---- Finish shopping / start payment ----

async function finishShopping() {
  const status = document.getElementById("status-text");
  const res = await fetch(`${BASE_URL}/api/start-payment`, { method: "POST" });
  const data = await res.json();

  if (data.ok) {
    status.textContent = "Payment started. Open the Payment tab or click the link.";
    status.className = "status ok";
    const link = document.getElementById("go-payment");
    if (link) link.classList.remove("hidden");
  } else {
    status.textContent = data.message || "Cannot start payment.";
    status.className = "status error";
  }
}


// ---- Init on each page ----

document.addEventListener("DOMContentLoaded", () => {
  const scanBtn = document.getElementById("scan-btn");
  const finishBtn = document.getElementById("finish-btn");
  const input = document.getElementById("barcode-input");

  if (scanBtn) scanBtn.addEventListener("click", scanBarcode);
  if (finishBtn) finishBtn.addEventListener("click", finishShopping);
  if (input) {
    input.addEventListener("keypress", e => {
      if (e.key === "Enter") {
        e.preventDefault();
        scanBarcode();
      }
    });
  }

  // Load cart data if cart table exists on this page
  if (document.getElementById("cart-body")) {
    fetchCart();
  }
});


// FINISH SHOPPING - Redirect to QR Payment
document.addEventListener('DOMContentLoaded', function() {
  const finishBtn = document.getElementById('finishBtn');
  if (finishBtn) {
    finishBtn.addEventListener('click', function() {
      // Save current cart state first
      fetchCart();
      // Redirect to payment page
      window.location.href = '/payment';
    });
  }
});

// Also handle any standalone Finish buttons on index.html
document.querySelectorAll('.finish-shopping-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    window.location.href = '/payment';
  });
});


// ---- Live weight display from backend (/api/get_weight) ----

async function fetchWeight() {
  try {
    const res = await fetch(`${BASE_URL}/api/get_weight`);
    const data = await res.json();
    const weight = data.weight;

    console.log("Weight:", weight);

    // Update UI element showing weight
    const el = document.getElementById("weight_value");
    if (el) {
      el.textContent = weight.toFixed(2) + " g";
    }
  } catch (err) {
    console.error("Error fetching weight", err);
  }
}

// Call periodically (e.g. every 1 second)
setInterval(fetchWeight, 1000);
