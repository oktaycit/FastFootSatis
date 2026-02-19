/**
 * FastFootSatış - Client-Side JavaScript
 * Real-time SocketIO communication and UI management
 */

// Global state
let socket = null;
let systemInfo = {};
let menuData = {};
let adisyonlar = {};
let currentMasa = null;
let currentItems = [];
let currentTotal = 0;

// DOM Elements
const elements = {
    companyName: null,
    terminalId: null,
    ipAddress: null,
    connectionStatus: null,
    menuContainer: null,
    paketSection: null,
    paketGrid: null,
    masaSection: null,
    masaGrid: null,
    currentMasaLabel: null,
    orderList: null,
    totalAmount: null,
    footerIp: null,
    footerTerminal: null,

    // Buttons
    btnPrint: null,
    btnCash: null,
    btnCard: null,
    btnCredit: null,
    btnTip: null,
    btnCari: null,
    btnReports: null,
    btnSettings: null,
    btnAbout: null,

    // Modal Elements
    paymentModal: null,
    closePaymentModal: null,
    modalTotalAmount: null,
    modalRemainingAmount: null,
    paymentNakit: null,
    paymentKart: null,
    paymentCari: null,
    customerSelectionDiv: null,
    customerSearch: null,
    customerResults: null,
    selectedCustomer: null,
    selectedCustomerDisplay: null,
    btnCancelPayment: null,
    btnFinalizePayment: null
};

/**
 * Initialize application
 */
function init() {
    // Get DOM elements
    Object.keys(elements).forEach(key => {
        const element = document.getElementById(key);
        if (element) {
            elements[key] = element;
        }
    });

    // Connect to SocketIO server
    connectToServer();

    // Setup event listeners
    setupEventListeners();

    console.log('✅ Application initialized');
}

/**
 * Connect to SocketIO server
 */
function connectToServer() {
    socket = io({
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 10
    });

    // Connection events
    socket.on('connect', onConnect);
    socket.on('disconnect', onDisconnect);
    socket.on('error', onError);

    // Data events
    socket.on('initial_data', onInitialData);
    socket.on('masa_selected', onMasaSelected);
    socket.on('masa_update', onMasaUpdate);
    socket.on('payment_completed', onPaymentCompleted);
    socket.on('success', onSuccess);
    socket.on('error', onError);

    console.log('🔌 Connecting to server...');
}

/**
 * Socket event handlers
 */
function onConnect() {
    console.log('✅ Connected to server');
    updateConnectionStatus(true);
}

function onDisconnect() {
    console.log('❌ Disconnected from server');
    updateConnectionStatus(false);
}

function onError(error) {
    console.error('❌ Socket error:', error);
    showNotification(error.message || 'Bir hata oluştu', 'error');
}

function onInitialData(data) {
    console.log('📦 Initial data received:', data);

    // Store data
    systemInfo = data.system || {};
    menuData = data.menu || {};
    adisyonlar = data.adisyonlar || {};

    // Update UI
    updateSystemInfo();
    renderMenu();
    renderTables();
}

function onMasaSelected(data) {
    console.log('✅ Masa selected:', data);
    currentMasa = data.masa;
    currentItems = data.items || [];
    currentTotal = data.total || 0;

    updateOrderDisplay();
}

function onMasaUpdate(data) {
    console.log('🔄 Masa update:', data);

    // Update adisyonlar
    adisyonlar[data.masa] = data.items || [];

    // If this is our current masa, update display
    if (data.masa === currentMasa) {
        currentItems = data.items || [];
        currentTotal = data.total || 0;
        updateOrderDisplay();
    }

    // Update table buttons
    updateTableButton(data.masa);
}

function onPaymentCompleted(data) {
    console.log('💰 Payment completed:', data);

    // Clear adisyon
    adisyonlar[data.masa] = [];

    // If this is our current masa, clear display
    if (data.masa === currentMasa) {
        currentItems = [];
        currentTotal = 0;
        updateOrderDisplay();

        // YENİ: Ödeme tamamlandığında modalı kapat
        if (typeof closePaymentModal === 'function') {
            closePaymentModal();
        }
    }

    // Update table button
    updateTableButton(data.masa);

    showNotification(`${data.type} ödemesi başarıyla alındı!`, 'success');
}

function onSuccess(data) {
    showNotification(data.message, 'success');
}

/**
 * Update UI functions
 */
function updateConnectionStatus(connected) {
    if (elements.connectionStatus) {
        elements.connectionStatus.style.color = connected ? '#2ecc71' : '#e74c3c';
    }
}

function updateSystemInfo() {
    if (elements.companyName && systemInfo.company_name) {
        elements.companyName.textContent = systemInfo.company_name;
    }

    if (elements.terminalId && systemInfo.terminal_id) {
        elements.terminalId.textContent = `Terminal ${systemInfo.terminal_id}`;
    }

    if (elements.ipAddress && systemInfo.ip) {
        elements.ipAddress.textContent = `IP: ${systemInfo.ip}`;
    }

    if (elements.footerIp && systemInfo.ip) {
        elements.footerIp.textContent = `📡 IP: ${systemInfo.ip}`;
    }

    if (elements.footerTerminal && systemInfo.terminal_id) {
        elements.footerTerminal.textContent = `🆔 Terminal ${systemInfo.terminal_id}`;
    }
}

function renderMenu() {
    if (!elements.menuContainer) return;

    elements.menuContainer.innerHTML = '';

    Object.keys(menuData).forEach((category, index) => {
        const categoryDiv = document.createElement('div');
        categoryDiv.className = 'menu-category';

        const categoryTitle = document.createElement('div');
        categoryTitle.className = 'category-title';
        categoryTitle.textContent = category;
        categoryTitle.style.background = getCategoryColor(index);
        categoryDiv.appendChild(categoryTitle);

        const itemsDiv = document.createElement('div');
        itemsDiv.className = 'menu-items';

        menuData[category].forEach(item => {
            const [name, price] = item;
            const itemBtn = document.createElement('button');
            itemBtn.className = 'menu-item';
            itemBtn.style.background = `linear-gradient(135deg, ${getCategoryColor(index)}, ${darkenColor(getCategoryColor(index))})`;

            itemBtn.innerHTML = `
                <span class="item-name">${name}</span>
                <span class="item-price">${price.toFixed(2)} TL</span>
            `;

            itemBtn.onclick = () => addItemToOrder(name, price);
            itemsDiv.appendChild(itemBtn);
        });

        categoryDiv.appendChild(itemsDiv);
        elements.menuContainer.appendChild(categoryDiv);
    });
}

function renderTables() {
    // Paket section
    if (systemInfo.paket_sayisi > 0) {
        elements.paketSection.style.display = 'block';
        elements.paketGrid.innerHTML = '';

        for (let i = 1; i <= systemInfo.paket_sayisi; i++) {
            const masa = `Paket ${i}`;
            const btn = createTableButton(masa, true);
            elements.paketGrid.appendChild(btn);
        }
    }

    // Masa section
    if (systemInfo.masa_sayisi > 0) {
        elements.masaSection.style.display = 'block';
        elements.masaGrid.innerHTML = '';

        for (let i = 1; i <= systemInfo.masa_sayisi; i++) {
            const masa = `Masa ${i}`;
            const btn = createTableButton(masa, false);
            elements.masaGrid.appendChild(btn);
        }
    }
}

function createTableButton(masa, isPaket) {
    const btn = document.createElement('button');
    btn.className = 'table-btn';
    btn.id = `btn-${masa.replace(' ', '-')}`;

    if (isPaket) {
        btn.classList.add('paket');
    }

    const items = adisyonlar[masa] || [];
    const total = items.reduce((sum, item) => sum + (item.adet * item.fiyat), 0);

    if (total > 0) {
        btn.classList.add('occupied');
        btn.innerHTML = `<div>${masa}</div><div>${total.toFixed(2)} TL</div>`;
    } else {
        btn.textContent = masa;
    }

    btn.onclick = () => selectMasa(masa);

    return btn;
}

function updateTableButton(masa) {
    const btnId = `btn-${masa.replace(' ', '-')}`;
    const btn = document.getElementById(btnId);

    if (!btn) return;

    const items = adisyonlar[masa] || [];
    const total = items.reduce((sum, item) => sum + (item.adet * item.fiyat), 0);

    if (total > 0) {
        btn.classList.add('occupied');
        btn.innerHTML = `<div>${masa}</div><div>${total.toFixed(2)} TL</div>`;
    } else {
        btn.classList.remove('occupied');
        btn.textContent = masa;
    }
}

function selectMasa(masa) {
    currentMasa = masa;

    // Update selection visual
    document.querySelectorAll('.table-btn').forEach(btn => {
        btn.classList.remove('selected');
    });

    const btnId = `btn-${masa.replace(' ', '-')}`;
    const btn = document.getElementById(btnId);
    if (btn) {
        btn.classList.add('selected');
    }

    // Notify server
    socket.emit('select_masa', { masa: masa });

    // Update label
    if (elements.currentMasaLabel) {
        elements.currentMasaLabel.textContent = masa;
    }
}

function updateOrderDisplay() {
    if (!elements.orderList) return;

    if (currentItems.length === 0) {
        elements.orderList.innerHTML = '<div class="empty-state"><p>Sipariş yok</p></div>';
    } else {
        elements.orderList.innerHTML = '';

        currentItems.forEach((item, index) => {
            const orderItem = document.createElement('div');
            orderItem.className = 'order-item';

            const itemTotal = item.adet * item.fiyat;
            const isIkram = item.tip === 'ikram';

            orderItem.innerHTML = `
                <div class="order-item-info">
                    <div class="order-item-name">${item.adet}x ${item.urun}${isIkram ? ' (İKRAM)' : ''}</div>
                </div>
                <div class="order-item-price">${itemTotal.toFixed(2)} TL</div>
            `;

            orderItem.onclick = () => removeItemFromOrder(index);
            orderItem.ondblclick = () => removeItemFromOrder(index);

            elements.orderList.appendChild(orderItem);
        });
    }

    // Update total
    if (elements.totalAmount) {
        elements.totalAmount.textContent = `${currentTotal.toFixed(2)} TL`;
    }
}

/**
 * Order management
 */
function addItemToOrder(urun, fiyat) {
    if (!currentMasa) {
        showNotification('Lütfen önce masa seçiniz!', 'warning');
        return;
    }

    socket.emit('add_item', {
        urun: urun,
        fiyat: fiyat
    });
}

function removeItemFromOrder(index) {
    socket.emit('remove_item', { index: index });
}

/**
 * Payment functions
 */
function processPayment(type) {
    console.log(`💰 processPayment called for: ${type}`);
    if (!currentMasa) {
        showNotification('Lütfen önce masa seçiniz!', 'warning');
        return;
    }

    if (currentItems.length === 0) {
        showNotification('Sipariş listesi boş!', 'warning');
        return;
    }

    const confirmMsg = `${type} ile ${currentTotal.toFixed(2)} TL ödeme alınacak. Onaylıyor musunuz?`;

    if (confirm(confirmMsg)) {
        console.log(`📤 Sending finalize_payment for: ${type}`);
        socket.emit('finalize_payment', { type: type });
    }
}

/**
 * Split Payment Modal Functions
 */
function openPaymentModal(prefillType = null) {
    if (!currentMasa) {
        showNotification('Lütfen önce masa seçiniz!', 'warning');
        return;
    }

    if (currentItems.length === 0) {
        showNotification('Sipariş listesi boş!', 'warning');
        return;
    }

    // Reset inputs
    elements.paymentNakit.value = '';
    elements.paymentKart.value = '';
    elements.paymentCari.value = '';

    // Pre-fill if type provided
    if (prefillType === 'Nakit') elements.paymentNakit.value = currentTotal.toFixed(2);
    if (prefillType === 'Kredi Kartı') elements.paymentKart.value = currentTotal.toFixed(2);
    if (prefillType === 'Açık Hesap') elements.paymentCari.value = currentTotal.toFixed(2);

    elements.customerSearch.value = '';
    elements.selectedCustomer.value = '';
    elements.selectedCustomerDisplay.textContent = 'Henüz müşteri seçilmedi';
    elements.customerSelectionDiv.style.display = prefillType === 'Açık Hesap' ? 'block' : 'none';

    // Show modal
    elements.paymentModal.style.display = 'block';

    // Update totals
    elements.modalTotalAmount.textContent = `${currentTotal.toFixed(2)} TL`;
    updateRemainingAmount();
}

function closePaymentModal() {
    elements.paymentModal.style.display = 'none';
}

function updateRemainingAmount() {
    const nakit = parseFloat(elements.paymentNakit.value) || 0;
    const kart = parseFloat(elements.paymentKart.value) || 0;
    const cari = parseFloat(elements.paymentCari.value) || 0;

    const paid = nakit + kart + cari;
    const remaining = currentTotal - paid;

    elements.modalRemainingAmount.textContent = `${remaining.toFixed(2)} TL`;

    if (remaining < 0) {
        elements.modalRemainingAmount.style.color = '#e74c3c';
    } else if (remaining === 0) {
        elements.modalRemainingAmount.style.color = '#27ae60';
    } else {
        elements.modalRemainingAmount.style.color = '#f39c12';
    }

    // Show/hide customer selection if Cari is entered
    if (cari > 0) {
        elements.customerSelectionDiv.style.display = 'block';
    } else {
        elements.customerSelectionDiv.style.display = 'none';
    }
}

function handlePaymentInputFocus(input) {
    const val = parseFloat(input.value) || 0;
    if (val === 0) {
        const nakit = input === elements.paymentNakit ? 0 : (parseFloat(elements.paymentNakit.value) || 0);
        const kart = input === elements.paymentKart ? 0 : (parseFloat(elements.paymentKart.value) || 0);
        const cari = input === elements.paymentCari ? 0 : (parseFloat(elements.paymentCari.value) || 0);

        const otherPaid = nakit + kart + cari;
        const remaining = Math.max(0, currentTotal - otherPaid);

        if (remaining > 0) {
            input.value = remaining.toFixed(2);
            updateRemainingAmount();
            input.select(); // Select the text for easy editing
        }
    }
}

async function searchCustomers() {
    const query = elements.customerSearch.value.toLowerCase();
    if (query.length < 2) {
        elements.customerResults.style.display = 'none';
        return;
    }

    try {
        const response = await fetch('/api/cari/hesaplar');
        const data = await response.json();

        if (data.success) {
            const results = data.hesaplar.filter(h =>
                h.cari_isim.toLowerCase().includes(query)
            );

            renderCustomerResults(results);
        }
    } catch (err) {
        console.error('Customer fetch error:', err);
    }
}

function renderCustomerResults(results) {
    elements.customerResults.innerHTML = '';

    if (results.length === 0) {
        const noResult = document.createElement('div');
        noResult.className = 'result-item';
        noResult.textContent = 'Yeni müşteri olarak ekle...';
        noResult.onclick = () => selectCustomer(elements.customerSearch.value, true);
        elements.customerResults.appendChild(noResult);
    } else {
        results.forEach(h => {
            const item = document.createElement('div');
            item.className = 'result-item';
            item.textContent = h.cari_isim;
            item.onclick = () => selectCustomer(h.cari_isim);
            elements.customerResults.appendChild(item);
        });
    }

    elements.customerResults.style.display = 'block';
}

function selectCustomer(name, isNew = false) {
    elements.selectedCustomer.value = name;
    elements.selectedCustomerDisplay.textContent = isNew ? `Yeni: ${name}` : name;
    elements.customerResults.style.display = 'none';
    elements.customerSearch.value = name;
}

function finalizeSplitPayment() {
    const nakit = parseFloat(elements.paymentNakit.value) || 0;
    const kart = parseFloat(elements.paymentKart.value) || 0;
    const cari = parseFloat(elements.paymentCari.value) || 0;

    const total = nakit + kart + cari;

    if (total === 0) {
        showNotification('Ödeme tutarı girilmedi!', 'warning');
        return;
    }

    if (Math.abs(total - currentTotal) > 0.01) {
        if (!confirm(`Girilen toplam (${total.toFixed(2)}) sipariş tutarından (${currentTotal.toFixed(2)}) farklı. Devam etmek istiyor musunuz?`)) {
            return;
        }
    }

    const payments = [];
    if (nakit > 0) payments.push({ type: 'Nakit', amount: nakit });
    if (kart > 0) payments.push({ type: 'Kredi Kartı', amount: kart });
    if (cari > 0) {
        const customer = elements.selectedCustomer.value;
        if (!customer) {
            showNotification('Lütfen Cari hesap için bir müşteri seçiniz!', 'warning');
            return;
        }
        payments.push({ type: 'Açık Hesap', amount: cari, customer: customer });
    }

    socket.emit('finalize_payment', { payments: payments });
    closePaymentModal();
}

/**
 * Event listeners setup
 */
function setupEventListeners() {
    if (elements.btnCash) {
        elements.btnCash.onclick = () => {
            console.log('💵 btnCash clicked -> opening modal with Nakit prefill');
            openPaymentModal('Nakit');
        };
    }

    if (elements.btnCard) {
        elements.btnCard.onclick = () => {
            console.log('💳 btnCard clicked -> opening modal with Kart prefill');
            openPaymentModal('Kredi Kartı');
        };
    }

    if (elements.btnCredit) {
        elements.btnCredit.onclick = () => {
            console.log('📝 btnCredit clicked -> opening modal with Cari prefill');
            openPaymentModal('Açık Hesap');
        };
    }

    if (elements.btnTip) {
        elements.btnTip.onclick = () => {
            showNotification('Bahşiş özelliği yakında eklenecek!', 'info');
        };
    }

    if (elements.btnPrint) {
        elements.btnPrint.onclick = () => {
            showNotification('Fiş yazdırma özelliği yakında eklenecek!', 'info');
        };
    }

    if (elements.btnCari) {
        elements.btnCari.onclick = () => {
            showNotification('Cari yönetimi özelliği yakında eklenecek!', 'info');
        };
    }

    if (elements.btnReports) {
        elements.btnReports.onclick = () => {
            showNotification('Rapor özelliği yakında eklenecek!', 'info');
        };
    }

    if (elements.btnSettings) {
        elements.btnSettings.onclick = () => {
            showNotification('Ayarlar özelliği yakında eklenecek!', 'info');
        };
    }

    if (elements.btnAbout) {
        elements.btnAbout.onclick = () => {
            alert(`FastFootSatış\nRestoran Yönetim Sistemi\n\nVersiyon: 1.0\nIP: ${systemInfo.ip || '---'}\nTerminal: ${systemInfo.terminal_id || '1'}`);
        };
    }

    // Modal & Payment Events
    if (elements.btnCredit) {
        elements.btnCredit.onclick = () => {
            console.log('📝 btnCredit clicked -> opening modal');
            openPaymentModal();
        };
    }

    if (elements.closePaymentModal) {
        elements.closePaymentModal.onclick = () => closePaymentModal();
    }

    if (elements.btnCancelPayment) {
        elements.btnCancelPayment.onclick = () => closePaymentModal();
    }

    if (elements.btnFinalizePayment) {
        elements.btnFinalizePayment.onclick = () => finalizeSplitPayment();
    }

    if (elements.paymentNakit) {
        elements.paymentNakit.oninput = () => updateRemainingAmount();
        elements.paymentNakit.onfocus = () => handlePaymentInputFocus(elements.paymentNakit);
    }
    if (elements.paymentKart) {
        elements.paymentKart.oninput = () => updateRemainingAmount();
        elements.paymentKart.onfocus = () => handlePaymentInputFocus(elements.paymentKart);
    }
    if (elements.paymentCari) {
        elements.paymentCari.oninput = () => updateRemainingAmount();
        elements.paymentCari.onfocus = () => handlePaymentInputFocus(elements.paymentCari);
    }

    if (elements.customerSearch) {
        elements.customerSearch.oninput = () => searchCustomers();
    }

    // Close modal on outside click
    window.onclick = (event) => {
        if (event.target == elements.paymentModal) {
            closePaymentModal();
        }
    };
}

/**
 * Utility functions
 */
function getCategoryColor(index) {
    const colors = [
        '#3498db', '#e67e22', '#2ecc71', '#9b59b6',
        '#f1c40f', '#1abc9c', '#e74c3c', '#34495e'
    ];
    return colors[index % colors.length];
}

function darkenColor(color) {
    // Simple color darkening (reduce RGB values by 20%)
    const hex = color.replace('#', '');
    const r = Math.max(0, parseInt(hex.substr(0, 2), 16) - 30);
    const g = Math.max(0, parseInt(hex.substr(2, 2), 16) - 30);
    const b = Math.max(0, parseInt(hex.substr(4, 2), 16) - 30);
    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

function showNotification(message, type = 'info') {
    // Simple alert for now - can be enhanced with toast notifications
    const icon = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️'
    }[type] || 'ℹ️';

    alert(`${icon} ${message}`);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', init);
