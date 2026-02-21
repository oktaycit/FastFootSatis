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
let selectedItemIndices = [];
let isSelectivePayment = false;

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
    btnFinalizePayment: null,
    btnPaySelected: null,
    splitButtonsArea: null,
    selectedCount: null,
    btnSplitEqually: null,

    // Caller ID Popup
    cidPopup: null,
    cidName: null,
    cidPhone: null,
    cidAddress: null,
    cidHistoryList: null,
    cidBalance: null,
    btnCidCreateOrder: null
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
    socket.on('system_info', onSystemInfo);
    socket.on('adisyonlar_update', onAdisyonlarUpdate);
    socket.on('masa_selected', onMasaSelected);
    socket.on('masa_update', onMasaUpdate);
    socket.on('payment_completed', onPaymentCompleted);
    socket.on('incoming_call', onIncomingCall);
    socket.on('success', onSuccess);
    socket.on('error', onError);
    socket.on('new_online_order', onNewOnlineOrder);

    // New: Order ready notification
    socket.on('order_ready', (data) => {
        showOrderReadyNotification(data);
    });

    console.log('🔌 Connecting to server...');
}

/**
 * Show notification for ready orders
 */
function showOrderReadyNotification(data) {
    console.log('🔔 Order ready notification:', data);

    // Play sound if possible
    try {
        const audio = new Audio('https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3');
        audio.play().catch(e => console.log('Audio play failed:', e));
    } catch (e) {
        console.warn('Notification sound failed');
    }

    // Show visual status
    if (typeof showNotification === 'function') {
        showNotification(data.message, 'success');
    } else {
        alert(data.message);
    }
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

    // Re-enable payment button if failed
    if (elements.btnFinalizePayment) {
        elements.btnFinalizePayment.disabled = false;
        elements.btnFinalizePayment.textContent = '✅ Ödemeyi Tamamla';
    }
}

function onSystemInfo(data) {
    console.log('📊 System info update:', data);
    systemInfo = data;
    updateSystemInfo();
}

function onInitialData(data) {
    console.log('📦 Initial data received:', data);

    // Store data
    systemInfo = data.system || {};
    menuData = data.menu || {};
    adisyonlar = data.adisyonlar || {};

    // Check for terminal role override in URL or localStorage
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('role')) {
        const role = urlParams.get('role');
        localStorage.setItem('terminal_role', role);
        console.log(`🎭 Role set from URL: ${role}`);
    }

    const currentRole = localStorage.getItem('terminal_role') || 'kasa';
    const isTerminal = (currentRole === 'terminal');

    // Update UI
    updateSystemInfo();
    renderMenu();
    renderTables();

    // Apply role restrictions
    if (isTerminal) {
        applyTerminalRestrictions();
    }
}

/**
 * Apply restrictions for non-kasa terminals
 */
function applyTerminalRestrictions() {
    console.log('🛡️ Applying terminal restrictions (Checkout disabled)');

    // Hide payment buttons
    const paymentButtons = document.querySelector('.payment-buttons');
    if (paymentButtons) paymentButtons.style.display = 'none';

    // Hide management buttons
    const managementToHide = ['btnCari', 'btnSettings', 'btnTerminals'];
    managementToHide.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            const link = el.closest('a');
            if (link) link.style.display = 'none';
            else el.style.display = 'none';
        }
    });

    // Hide split buttons
    if (elements.splitButtonsArea) elements.splitButtonsArea.style.display = 'none';

    // Update terminal text to show it's a terminal
    if (elements.terminalId) {
        elements.terminalId.textContent += ' (Sipariş Terminali)';
        elements.terminalId.style.color = '#f39c12';
    }

    // Disable payment functions at code level
    const originalOpenPaymentModal = window.openPaymentModal;
    window.openPaymentModal = function () {
        showNotification('Bu terminal yetkili değildir!', 'error');
    };
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

    // If this is our current masa, clear display ONLY IF NOT partial
    if (data.masa === currentMasa && !data.is_partial) {
        currentItems = [];
        currentTotal = 0;
        updateOrderDisplay();

        if (typeof closePaymentModal === 'function') {
            closePaymentModal();
        }
    }

    // Seçimleri temizle
    selectedItemIndices = [];
    updateSplitButtons();

    // Update table button
    updateTableButton(data.masa);

    showNotification(`${data.type} ödemesi başarıyla alındı!`, 'success');
}

function onNewOnlineOrder(data) {
    console.log('🌐 New online order:', data);

    // Play notification sound
    try {
        const audio = new Audio('https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3');
        audio.play().catch(e => console.log('Audio play failed:', e));
    } catch (e) { }

    showOnlineOrderPopup(data);
}

function showOnlineOrderPopup(data) {
    const popup = document.getElementById('onlineOrderPopup');
    if (!popup) return;

    document.getElementById('ooPlatform').textContent = data.platform.toUpperCase();
    document.getElementById('ooPlatform').className = `oo-platform ${data.platform.toLowerCase()}`;
    document.getElementById('ooCustomer').textContent = data.customer || 'Bilinmeyen Müşteri';
    document.getElementById('ooMasa').textContent = data.masa;

    popup.classList.add('show');

    // Auto close after 10 seconds
    setTimeout(() => {
        popup.classList.remove('show');
    }, 10000);
}

function closeOnlineOrderPopup() {
    const popup = document.getElementById('onlineOrderPopup');
    if (popup) popup.classList.remove('show');
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

    // Reset selection on masa switch
    selectedItemIndices = [];
    updateSplitButtons();
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
            const isHazir = item.durum === 'hazir';

            orderItem.innerHTML = `
                <div class="order-item-info" style="flex-grow: 1;">
                    <div class="order-item-name">
                        ${isHazir ? '<span style="color: #2ecc71; font-weight: bold; font-size: 10px;">[HAZIR] </span>' : ''}
                        ${item.adet}x ${item.urun}${isIkram ? ' (İKRAM)' : ''}
                    </div>
                    <div style="font-size: 10px; color: #777;">${item.garson || 'Bilinmiyor'} - ${item.saat || ''}</div>
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div class="order-item-price">${itemTotal.toFixed(2)} TL</div>
                    ${!isHazir && item.uid ? `
                        <button class="btn-cancel-small" onclick="cancelItem('${item.uid}', event)" 
                                style="background: #e74c3c; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 10px; cursor: pointer;">
                            İPTAL
                        </button>
                    ` : ''}
                </div>
            `;

            if (selectedItemIndices.includes(index)) {
                orderItem.classList.add('selected');
            }

            orderItem.onclick = (e) => {
                if (!e.target.closest('button')) {
                    toggleItemSelection(index);
                }
            };

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

function cancelItem(uid, event) {
    if (event) event.stopPropagation();

    if (!currentMasa) return;

    if (confirm('Bu siparişi iptal etmek istediğinize emin misiniz?')) {
        console.log(`🗑️ Cancelling item ${uid} for ${currentMasa}`);
        socket.emit('cancel_item', {
            masa: currentMasa,
            uid: uid
        });
    }
}

function toggleItemSelection(index) {
    const pos = selectedItemIndices.indexOf(index);
    if (pos === -1) {
        selectedItemIndices.push(index);
    } else {
        selectedItemIndices.splice(pos, 1);
    }
    updateOrderDisplay();
    updateSplitButtons();
}

function updateSplitButtons() {
    if (!elements.splitButtonsArea) return;

    if (selectedItemIndices.length > 0) {
        elements.splitButtonsArea.style.display = 'block';
        elements.selectedCount.textContent = selectedItemIndices.length;
    } else {
        elements.splitButtonsArea.style.display = 'none';
    }
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
function getCurrentPaymentTotal() {
    if (isSelectivePayment) {
        return currentItems
            .filter((_, i) => selectedItemIndices.includes(i))
            .reduce((sum, item) => sum + (item.adet * item.fiyat), 0);
    }
    return currentTotal;
}

function openPaymentModal(prefillType = null, isSelective = false) {
    if (!currentMasa) {
        showNotification('Lütfen önce masa seçiniz!', 'warning');
        return;
    }

    const itemsToPay = isSelective ? currentItems.filter((_, i) => selectedItemIndices.includes(i)) : currentItems;

    if (itemsToPay.length === 0) {
        showNotification('Sipariş listesi boş!', 'warning');
        return;
    }

    isSelectivePayment = isSelective;
    const itemsTotal = itemsToPay.reduce((sum, item) => sum + (item.adet * item.fiyat), 0);

    // Reset inputs
    elements.paymentNakit.value = '';
    elements.paymentKart.value = '';
    elements.paymentCari.value = '';

    // Pre-fill if type provided
    if (prefillType === 'Nakit') elements.paymentNakit.value = itemsTotal.toFixed(2);
    if (prefillType === 'Kredi Kartı') elements.paymentKart.value = itemsTotal.toFixed(2);
    if (prefillType === 'Açık Hesap') elements.paymentCari.value = itemsTotal.toFixed(2);

    elements.customerSearch.value = '';
    elements.selectedCustomer.value = '';
    elements.selectedCustomerDisplay.textContent = 'Henüz müşteri seçilmedi';
    elements.customerSelectionDiv.style.display = prefillType === 'Açık Hesap' ? 'block' : 'none';

    // Show modal
    elements.paymentModal.style.display = 'block';

    // Update totals
    elements.modalTotalAmount.textContent = `${itemsTotal.toFixed(2)} TL`;
    updateRemainingAmount(itemsTotal);
}

function closePaymentModal() {
    elements.paymentModal.style.display = 'none';
    isSelectivePayment = false;
}

function updateRemainingAmount(overrideTotal = null) {
    const nakit = parseFloat(elements.paymentNakit.value) || 0;
    const kart = parseFloat(elements.paymentKart.value) || 0;
    const cari = parseFloat(elements.paymentCari.value) || 0;

    const total = overrideTotal !== null ? overrideTotal : getCurrentPaymentTotal();

    const paid = nakit + kart + cari;
    const remaining = total - paid;

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
        const total = getCurrentPaymentTotal();
        const nakit = input === elements.paymentNakit ? 0 : (parseFloat(elements.paymentNakit.value) || 0);
        const kart = input === elements.paymentKart ? 0 : (parseFloat(elements.paymentKart.value) || 0);
        const cari = input === elements.paymentCari ? 0 : (parseFloat(elements.paymentCari.value) || 0);

        const otherPaid = nakit + kart + cari;
        const remaining = Math.max(0, total - otherPaid);

        if (remaining > 0) {
            input.value = remaining.toFixed(2);
            updateRemainingAmount();
            input.select(); // Select the text for easy editing
        }
    }
}

function balancePaymentInputs(changedInput) {
    const total = getCurrentPaymentTotal();
    const nakit = parseFloat(elements.paymentNakit.value) || 0;
    const kart = parseFloat(elements.paymentKart.value) || 0;
    const cari = parseFloat(elements.paymentCari.value) || 0;

    const currentSum = nakit + kart + cari;

    if (currentSum > total) {
        let excess = currentSum - total;

        // Diğer alanları azaltarak dengele (Nakit > Kart > Cari sırasıyla, ama değişen alanı atla)
        const possibleInputs = [
            { el: elements.paymentNakit, val: nakit },
            { el: elements.paymentKart, val: kart },
            { el: elements.paymentCari, val: cari }
        ];

        // Mevcut alanı listeden çıkar
        const inputsToAdjust = possibleInputs.filter(item => item.el !== changedInput && item.val > 0);

        for (let item of inputsToAdjust) {
            if (excess <= 0.001) break;
            let reduceBy = Math.min(item.val, excess);
            let newVal = item.val - reduceBy;
            item.el.value = newVal > 0.001 ? newVal.toFixed(2) : '';
            excess -= reduceBy;
        }
    }
    updateRemainingAmount();
}

function splitEqually() {
    const countStr = prompt("Hesap kaç kişiye bölünecek?", "2");
    const count = parseInt(countStr);

    if (isNaN(count) || count <= 0) return;

    const total = getCurrentPaymentTotal();
    const perPerson = total / count;

    // Default to Cash
    elements.paymentNakit.value = perPerson.toFixed(2);
    elements.paymentKart.value = '';
    elements.paymentCari.value = '';

    updateRemainingAmount(total);
    showNotification(`Kişi başı: ${perPerson.toFixed(2)} TL. Ödeme türünü değiştirebilirsiniz.`, 'info');
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

    if (Math.abs(total - currentTotal) > 0.01 && !isSelectivePayment) {
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

    const currentRole = localStorage.getItem('terminal_role') || 'kasa';
    const payload = {
        payments: payments,
        role: currentRole
    };
    if (isSelectivePayment) {
        payload.item_indices = selectedItemIndices;
    }

    if (systemInfo.pos_enabled && kart > 0) {
        elements.btnFinalizePayment.disabled = true;
        elements.btnFinalizePayment.innerHTML = '⏳ POS Bekleniyor...';
        socket.emit('finalize_payment', payload);
        // Modal will be closed by onPaymentCompleted upon success
    } else {
        socket.emit('finalize_payment', payload);
        closePaymentModal();
    }
}

/**
 * Handle direct payment buttons (non-modal legacy)
 */
function processPayment(type) {
    if (!currentMasa) {
        showNotification('Lütfen önce masa seçiniz!', 'warning');
        return;
    }
    const currentRole = localStorage.getItem('terminal_role') || 'kasa';
    if (currentRole === 'terminal') {
        showNotification('Bu terminal yetkili değildir!', 'error');
        return;
    }
    // ... rest of processPayment if needed, but the UI already hides it
}

/**
 * Event listeners setup
 */
function setupEventListeners() {
    if (elements.btnCash) {
        elements.btnCash.onclick = () => {
            const isSelective = selectedItemIndices.length > 0;
            console.log(`💵 btnCash clicked -> opening modal with Nakit prefill (Selective: ${isSelective})`);
            openPaymentModal('Nakit', isSelective);
        };
    }

    if (elements.btnCard) {
        elements.btnCard.onclick = () => {
            const isSelective = selectedItemIndices.length > 0;
            console.log(`💳 btnCard clicked -> opening modal with Kart prefill (Selective: ${isSelective})`);
            openPaymentModal('Kredi Kartı', isSelective);
        };
    }

    if (elements.btnCredit) {
        elements.btnCredit.onclick = () => {
            const isSelective = selectedItemIndices.length > 0;
            console.log(`📝 btnCredit clicked -> opening modal with Cari prefill (Selective: ${isSelective})`);
            openPaymentModal('Açık Hesap', isSelective);
        };
    }

    if (elements.btnPrint) {
        elements.btnPrint.onclick = () => {
            if (!currentMasa) {
                showNotification('Lütfen önce masa seçiniz!', 'warning');
                return;
            }
            if (currentItems.length === 0) {
                showNotification('Yazdırılacak sipariş yok!', 'warning');
                return;
            }
            socket.emit('print_receipt', { masa: currentMasa });
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
        elements.paymentNakit.oninput = () => {
            balancePaymentInputs(elements.paymentNakit);
        };
        elements.paymentNakit.onfocus = () => handlePaymentInputFocus(elements.paymentNakit);
    }
    if (elements.paymentKart) {
        elements.paymentKart.oninput = () => {
            balancePaymentInputs(elements.paymentKart);
        };
        elements.paymentKart.onfocus = () => handlePaymentInputFocus(elements.paymentKart);
    }
    if (elements.paymentCari) {
        elements.paymentCari.oninput = () => {
            balancePaymentInputs(elements.paymentCari);
        };
        elements.paymentCari.onfocus = () => handlePaymentInputFocus(elements.paymentCari);
    }

    if (elements.customerSearch) {
        elements.customerSearch.oninput = () => searchCustomers();
    }

    if (elements.btnPaySelected) {
        elements.btnPaySelected.onclick = () => openPaymentModal(null, true);
    }

    if (elements.btnSplitEqually) {
        elements.btnSplitEqually.onclick = () => splitEqually();
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
/**
 * Handle incoming call from Caller ID
 */
function onIncomingCall(data) {
    console.log('📞 Incoming call:', data);

    const { phone, customer, history } = data;

    // Update Popup UI
    elements.cidPhone.innerText = formatPhone(phone);

    if (customer) {
        elements.cidName.innerText = customer.cari_isim;
        elements.cidAddress.innerText = customer.adres || 'Adres bilgisi bulunamadı.';
        elements.cidBalance.innerText = customer.bakiye !== undefined ? `BAKİYE: ${customer.bakiye.toFixed(2)} TL` : '';
    } else {
        elements.cidName.innerText = 'Yeni Müşteri';
        elements.cidAddress.innerText = 'Adres bilgisi bulunamadı.';
        elements.cidBalance.innerText = '';
    }

    // Update History
    elements.cidHistoryList.innerHTML = '';
    if (history && history.length > 0) {
        history.forEach(item => {
            const div = document.createElement('div');
            div.className = 'cid-history-item';
            div.innerHTML = `
                <div>
                    <div>${item.urun} (x${item.adet})</div>
                    <div class="cid-history-date">${item.tarih}</div>
                </div>
                <div class="cid-history-price">${item.fiyat.toFixed(2)} TL</div>
            `;
            elements.cidHistoryList.appendChild(div);
        });
    } else {
        elements.cidHistoryList.innerHTML = '<div style="text-align:center; padding: 20px; color: #64748b; font-size: 13px;">Geçmiş sipariş bulunamadı.</div>';
    }

    // Setup Action
    elements.btnCidCreateOrder.onclick = () => createPaketOrderFromCid(phone, customer);

    // Show Popup
    elements.cidPopup.style.display = 'block';

    // Auto-close after 30 seconds
    if (window.cidTimeout) clearTimeout(window.cidTimeout);
    window.cidTimeout = setTimeout(closeCidPopup, 30000);
}

function closeCidPopup() {
    elements.cidPopup.style.display = 'none';
    if (window.cidTimeout) clearTimeout(window.cidTimeout);
}

function formatPhone(phone) {
    if (!phone) return '';
    phone = phone.replace(/\D/g, '');
    if (phone.length === 10) {
        return `0 (${phone.substring(0, 3)}) ${phone.substring(3, 6)} ${phone.substring(6, 8)} ${phone.substring(8, 10)}`;
    }
    return phone;
}

function createPaketOrderFromCid(phone, customer) {
    // Boş bir paket slotu bul
    const paketItems = elements.paketGrid.querySelectorAll('.table-btn');
    let emptyPaket = null;

    for (let btn of paketItems) {
        if (!btn.classList.contains('occupied')) {
            emptyPaket = btn;
            break;
        }
    }

    if (emptyPaket) {
        // Paketi seç
        emptyPaket.click();
        closeCidPopup();

        // Eğer müşteri kayıtlıysa, adisyon notuna veya başka bir yere bilgi eklenebilir
        // Ancak mevcut sistemde not alanı yok. 
        showToast(`${emptyPaket.innerText} seçildi. Sipariş alabilirsiniz.`, 'success');

        // Ödeme kısmında bu müşteriyi otomatik seçmek için bir ipucu bırakabiliriz
        if (customer) {
            window.activeCallCustomer = customer;
        }
    } else {
        showToast('Boş paket slotu bulunamadı!', 'error');
    }
}
