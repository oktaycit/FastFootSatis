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
    btnAbout: null
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
        socket.emit('finalize_payment', { type: type });
    }
}

/**
 * Event listeners setup
 */
function setupEventListeners() {
    if (elements.btnCash) {
        elements.btnCash.onclick = () => processPayment('Nakit');
    }

    if (elements.btnCard) {
        elements.btnCard.onclick = () => processPayment('Kredi Kartı');
    }

    if (elements.btnCredit) {
        elements.btnCredit.onclick = () => {
            showNotification('Cari hesap özelliği yakında eklenecek!', 'info');
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
