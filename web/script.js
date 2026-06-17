/**
 * Restoran - Client-Side JavaScript
 * Real-time SocketIO communication and UI management
 */

// Global state
let socket = null;
let systemInfo = {};
let menuData = {};
let portionStock = {};
let dailyMeals = { items: [], categories: [] };
let adisyonlar = {};
let tableNotes = {};
let reservationsPayload = { reservations: [], active_by_table: {}, active_count: 0, today_count: 0 };
let alertedReservationKeys = new Set();
let currentMasa = null;
let currentItems = [];
let currentTotal = 0;
let selectedItemKeys = [];
let isSelectivePayment = false;
let suppressCardSplitSync = false;
let paymentInProgress = false;
let paymentWaitTimer = null;
let activeShift = null;
let cashierOrderEntryOpen = false;
let operationsStatusTimer = null;
let operationsStatusInFlight = null;
let operationsStatusNextRefreshAt = 0;
let reservationAlertTimer = null;
let lastSyncedKasaId = null;
let customerAccountsCache = { expiresAt: 0, items: [] };
let customerSearchTimer = null;
const PAYMENT_METHODS = ['Nakit', 'Kredi Kartı', 'Açık Hesap'];
const Z_REPORT_HOLD_MS = 5000;
const FINALIZE_PAYMENT_LABEL = '✅ Ödemeyi Tamamla';
const PAYMENT_WAIT_TIMEOUT_MS = 150000;
const OPERATIONS_STATUS_REFRESH_MS = 30000;
const OPERATIONS_STATUS_MIN_REFRESH_MS = 5000;
const CUSTOMER_SEARCH_DEBOUNCE_MS = 200;
const CUSTOMER_ACCOUNTS_CACHE_MS = 30000;
const RESERVATION_ALERT_WINDOW_MINUTES = 60;
const STAFF_TABLES_PER_WAITER = 4;
const STAFFING_IGNORED_WAITER_NAMES = new Set([
    '',
    'kasa',
    'bilinmiyor',
    'ortak terminal',
    'musteri qr',
    'müşteri qr',
    'online siparis',
    'online sipariş'
]);

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));
}

function getPaketLabels() {
    if (Object.prototype.hasOwnProperty.call(systemInfo, 'paket_labels')) {
        return Array.isArray(systemInfo.paket_labels)
            ? systemInfo.paket_labels.map(label => String(label || '').trim()).filter(Boolean)
            : [];
    }

    const paketCount = Number(systemInfo.paket_sayisi || 0);
    return Array.from({ length: Math.max(0, paketCount) }, (_, index) => `Paket ${index + 1}`);
}

function isPaketMasa(masa) {
    return getPaketLabels().includes(String(masa || '').trim());
}

function getTableButtonId(masa) {
    return `btn-${encodeURIComponent(String(masa || '').trim()).replace(/%/g, '_')}`;
}

function normalizeTableNote(note) {
    return String(note || '').trim();
}

function getTableNote(masa) {
    return normalizeTableNote(tableNotes[String(masa || '').trim()]);
}

function setLocalTableNote(masa, note) {
    const masaAdi = String(masa || '').trim();
    if (!masaAdi) return;
    const cleanNote = normalizeTableNote(note);
    if (cleanNote) {
        tableNotes[masaAdi] = cleanNote;
    } else {
        delete tableNotes[masaAdi];
    }
}

function isMenuItemVisible(item) {
    if (!Array.isArray(item) || item.length <= 7) return true;
    const value = item[7];
    if (typeof value === 'boolean') return value;
    return !['0', 'false', 'hayir', 'hayır', 'no', 'off'].includes(String(value).trim().toLowerCase());
}

function isComplimentaryItem(item) {
    return (item?.tip || '') === 'ikram';
}

function isReadyItem(item) {
    return item && item.durum === 'hazir';
}

function isServedItem(item) {
    return item && item.durum === 'servis_edildi';
}

function isKitchenCancelableItem(item) {
    return !item?.durum || item.durum === 'mutfakta';
}

function getLineTotal(item) {
    const adet = Number(item?.adet || 0);
    const fiyat = Number(item?.fiyat || 0);
    return Math.max(0, adet) * Math.max(0, fiyat);
}

function getPayableTotal(items = currentItems) {
    return (items || []).reduce((sum, item) => (
        isComplimentaryItem(item) ? sum : sum + getLineTotal(item)
    ), 0);
}

function getComplimentaryTotal(items = currentItems) {
    return (items || []).reduce((sum, item) => (
        isComplimentaryItem(item) ? sum + getLineTotal(item) : sum
    ), 0);
}

function refreshCurrentTotal() {
    currentTotal = getPayableTotal(currentItems);
}

function resetFinalizePaymentButton() {
    paymentInProgress = false;
    if (paymentWaitTimer) {
        clearTimeout(paymentWaitTimer);
        paymentWaitTimer = null;
    }
    if (elements.btnFinalizePayment) {
        elements.btnFinalizePayment.disabled = false;
        elements.btnFinalizePayment.textContent = FINALIZE_PAYMENT_LABEL;
    }
}

function setFinalizePaymentWaiting(message = '⏳ ÖKC Bekleniyor...') {
    paymentInProgress = true;
    if (paymentWaitTimer) {
        clearTimeout(paymentWaitTimer);
    }
    if (elements.btnFinalizePayment) {
        elements.btnFinalizePayment.disabled = true;
        elements.btnFinalizePayment.textContent = message;
    }
    paymentWaitTimer = setTimeout(() => {
        resetFinalizePaymentButton();
        refreshCurrentMasaFromServer();
        showNotification('ÖKC yanıtı beklenenden uzun sürdü. Masa durumu sunucudan tekrar kontrol edildi.', 'warning');
    }, PAYMENT_WAIT_TIMEOUT_MS);
}

async function refreshCurrentMasaFromServer() {
    if (!currentMasa) return;
    try {
        const response = await fetch(`/api/adisyon/${encodeURIComponent(currentMasa)}`);
        if (!response.ok) return;
        const data = await response.json();
        adisyonlar[data.masa] = data.items || [];
        if (data.masa === currentMasa) {
            currentItems = data.items || [];
            currentTotal = Number(data.total ?? getPayableTotal(currentItems)) || 0;
            updateOrderDisplay();
            updateQuickSaleUI();
        }
        updateTableButton(data.masa);
        updateStaffingSummary();
    } catch (err) {
        console.error('Masa refresh failed:', err);
    }
}

function normalizePaymentMethod(value) {
    const normalized = String(value || '').trim().toLocaleLowerCase('tr-TR');
    if (PAYMENT_METHODS.includes(value)) return value;
    if (normalized === 'kart' || normalized === 'kredi karti' || normalized === 'kredi kartı') {
        return 'Kredi Kartı';
    }
    if (normalized === 'cari' || normalized === 'acik hesap' || normalized === 'açık hesap') {
        return 'Açık Hesap';
    }
    return 'Nakit';
}

function getDefaultPaymentMethod() {
    return normalizePaymentMethod(systemInfo.default_payment_method || 'Nakit');
}

function normalizeTerminalRole(value) {
    const role = String(value || '').trim().toLocaleLowerCase('tr-TR');
    if (role === 'terminal' || role === 'garson' || role === 'order' || role === 'siparis') {
        return 'terminal';
    }
    return 'kasa';
}

function captureTerminalRoleFromLocation() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('role')) {
        const role = normalizeTerminalRole(urlParams.get('role'));
        localStorage.setItem('terminal_role', role);
        console.log(`🎭 Role set from URL: ${role}`);
        return role;
    }
    if (window.location.pathname.includes('kasa-terminal')) {
        localStorage.setItem('terminal_role', 'kasa');
        return 'kasa';
    }
    return normalizeTerminalRole(localStorage.getItem('terminal_role') || 'kasa');
}

function getTerminalRole() {
    return normalizeTerminalRole(localStorage.getItem('terminal_role') || 'kasa');
}

function canEnterOrders() {
    return getTerminalRole() !== 'kasa' || cashierOrderEntryOpen;
}

// DOM Elements
const elements = {
    companyName: null,
    terminalId: null,
    connectionStatus: null,
    menuContainer: null,
    paketSection: null,
    paketGrid: null,
    masaSection: null,
    masaGrid: null,
    staffingSummary: null,
    staffingStatusDot: null,
    staffingRecommendation: null,
    staffingDetail: null,
    staffingActiveTables: null,
    staffingOccupancy: null,
    staffingActiveWaiters: null,
    staffingNeededWaiters: null,
    currentMasaLabel: null,
    tableNotePanel: null,
    tableNoteInput: null,
    btnSaveTableNote: null,
    orderList: null,
    totalAmount: null,
    complimentaryAmount: null,
    footerTerminal: null,

    // Buttons
    btnPrint: null,
    btnTotalPayment: null,
    btnOpenTablePicker: null,
    btnToggleOrderEntry: null,
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
    cardSplitPanel: null,
    cardSplitSummary: null,
    cardSplitRows: null,
    btnAddCardSplit: null,
    btnSplitCardsEqual: null,
    invoicePending: null,
    invoiceDocumentType: null,
    invoiceTaxId: null,
    invoiceSerialNo: null,
    invoiceNote: null,
    customerSelectionDiv: null,
    customerSearch: null,
    customerResults: null,
    selectedCustomer: null,
    selectedCustomerDisplay: null,
    btnCancelPayment: null,
    btnFinalizePayment: null,
    btnPaySelected: null,
    btnCompSelected: null,
    btnUncompSelected: null,
    btnCloseCompBill: null,
    splitButtonsArea: null,
    selectedCount: null,
    cashierQuickSale: null,
    operationsStatus: null,
    operationsStatusList: null,
    operationsStatusUpdated: null,
    quickSaleMasaHint: null,
    btnQuickWater: null,
    btnQuickDessert: null,
    quickDessertForm: null,
    quickDessertProduct: null,
    quickDessertGrams: null,
    btnQuickDessertAdd: null,
    quickDessertPreview: null,
    // Caller ID Popup
    cidPopup: null,
    cidName: null,
    cidPhone: null,
    cidAddress: null,
    cidHistoryList: null,
    cidBalance: null,
    btnCidCreateOrder: null,

    // Transfer Modal
    transferModal: null,
    closeTransferModal: null,
    transferTargetGrid: null,
    btnCancelTransfer: null,
    btnTransfer: null,
    tablePickerModal: null,
    closeTablePickerModal: null,
    tablePickerGrid: null,
    btnCancelTablePicker: null,

    // Courier Assignment
    courierAssignmentArea: null,
    courierSelect: null,
    btnAssignCourier: null,
    assignedCourierInfo: null,
    assignedCourierName: null,
    btnSendCourierInfo: null,
    orderResizer: null,
    resizerLeft: null,
    resizerRight: null,
    leftPanel: null,
    rightPanel: null
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

    // Also get panels if not explicitly ID'd
    elements.leftPanel = document.querySelector('.left-panel');
    elements.rightPanel = document.querySelector('.right-panel');

    // Connect to SocketIO server
    connectToServer();

    // Setup event listeners
    setupEventListeners();

    // Initialize resizer
    initResizer();
    initHorizontalResizers();
    startOperationsStatusPolling();
    startReservationAlertPolling();

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

    // Data events
    socket.on('initial_data', onInitialData);
    socket.on('system_info', onSystemInfo);
    socket.on('system_update', onSystemUpdate);
    socket.on('staffing_update', onStaffingUpdate);
    socket.on('adisyonlar_update', onAdisyonlarUpdate);
    socket.on('masa_selected', onMasaSelected);
    socket.on('masa_update', onMasaUpdate);
    socket.on('table_note_update', onTableNoteUpdate);
    socket.on('reservations_update', onReservationsUpdate);
    socket.on('reservation_menu_notice', onReservationMenuNotice);
    socket.on('payment_completed', onPaymentCompleted);
    socket.on('incoming_call', onIncomingCall);
    socket.on('success', onSuccess);
    socket.on('error', onError);
    socket.on('new_online_order', onNewOnlineOrder);
    socket.on('vardiya_update', onVardiyaUpdate);
    socket.on('portion_stock_update', onPortionStockUpdate);
    socket.on('daily_meals_update', onDailyMealsUpdate);

    // New: Order ready notification
    socket.on('order_ready', (data) => {
        showOrderReadyNotification(data);
    });

    socket.on('courier_assigned', onCourierAssigned);
    socket.on('courier_message_ready', onCourierMessageReady);

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

function getSelectedKasaId() {
    let kasaId = localStorage.getItem('kasa_id');
    if (!kasaId) {
        kasaId = "1";
        localStorage.setItem('kasa_id', kasaId);
        localStorage.setItem('kasa_ad', 'Kasa 1');
        console.log('📟 Default Kasa set: 1');
    }
    return parseInt(kasaId, 10);
}

function syncSelectedKasa({ force = false } = {}) {
    if (!socket || !socket.connected) return;

    const kasaId = getSelectedKasaId();
    if (Number.isFinite(kasaId) && kasaId > 0 && (force || lastSyncedKasaId !== kasaId)) {
        socket.emit('set_kasa', { kasa_id: kasaId });
        lastSyncedKasaId = kasaId;
    }
}

function onConnect() {
    console.log('✅ Connected to server');
    updateConnectionStatus(true);
    refreshOperationsStatus();

    // Kasa ID'sini bildir
    syncSelectedKasa({ force: true });
}

function onDisconnect() {
    console.log('❌ Disconnected from server');
    updateConnectionStatus(false);
    lastSyncedKasaId = null;
}

function onError(error) {
    console.error('❌ Socket error:', error);
    showNotification(error.message || 'Bir hata oluştu', 'error');
    resetFinalizePaymentButton();
}

function onSystemInfo(data) {
    console.log('📊 System info update:', data);
    systemInfo = data || {};
    updateSystemInfo();
    renderTables();
    refreshOperationsStatus();
}

function onSystemUpdate(data) {
    console.log('📊 System update:', data);
    if (!data || !hasSystemLayoutPayload(data)) return;

    systemInfo = { ...systemInfo, ...data };
    updateSystemInfo();
    renderTables();
    refreshOperationsStatus();
}

function onStaffingUpdate(data) {
    console.log('👥 Staffing update:', data);
    systemInfo = { ...systemInfo, ...(data || {}) };
    updateStaffingSummary();
}

function hasSystemLayoutPayload(data) {
    return Object.prototype.hasOwnProperty.call(data, 'masa_sayisi')
        || Object.prototype.hasOwnProperty.call(data, 'paket_sayisi')
        || Object.prototype.hasOwnProperty.call(data, 'paket_labels')
        || Object.prototype.hasOwnProperty.call(data, 'salons')
        || Object.prototype.hasOwnProperty.call(data, 'company_name')
        || Object.prototype.hasOwnProperty.call(data, 'terminal_id');
}

function onInitialData(data) {
    console.log('📦 Initial data received:', data);

    // Store data
    systemInfo = data.system || {};
    menuData = data.menu || {};
    portionStock = data.portion_stock || {};
    dailyMeals = data.daily_meals || dailyMeals;
    adisyonlar = data.adisyonlar || {};
    tableNotes = data.table_notes || {};
    reservationsPayload = normalizeReservationsPayload(data.reservations);
    activeShift = data.active_shift || activeShift || null;

    const currentRole = captureTerminalRoleFromLocation();

    // Update UI
    updateSystemInfo();
    renderMenu();
    renderTables();
    checkUpcomingReservationAlerts();
    updateVardiyaUI(); // İlk yüklemede vardiya durumunu yansıt
    updateTableNoteUI();
    syncSelectedKasa(); // Sunucudan kasa secimine gore guncel vardiyayi tekrar iste

    applyRoleProfile(currentRole);
    populateQuickDessertOptions();
    updateQuickSaleUI();
    refreshOperationsStatus();
}

function applyRoleProfile(role = getTerminalRole()) {
    document.body.classList.remove('cashier-terminal', 'order-terminal', 'cashier-order-entry');
    if (role === 'terminal') {
        cashierOrderEntryOpen = false;
        applyTerminalRestrictions();
        return;
    }
    applyCashierProfile();
}

function applyCashierProfile() {
    document.body.classList.add('cashier-terminal');
    const banner = document.getElementById('terminalModeBanner');
    if (banner) {
        banner.querySelector('strong').textContent = 'KASA HESAP TERMİNALİ';
        banner.querySelector('span').textContent = 'Sipariş girişi garson ekranlarında';
    }
    if (elements.currentMasaLabel && !currentMasa) {
        elements.currentMasaLabel.textContent = 'Hesap için masa seçiniz';
    }
    if (elements.terminalId) {
        elements.terminalId.style.color = '';
    }
    updateCashierOrderEntryUI();
    updateQuickSaleUI();
}

function updateCashierOrderEntryUI() {
    const isCashier = getTerminalRole() === 'kasa';
    const active = isCashier && cashierOrderEntryOpen;
    document.body.classList.toggle('cashier-order-entry', active);

    if (elements.btnToggleOrderEntry) {
        elements.btnToggleOrderEntry.style.display = isCashier ? '' : 'none';
        elements.btnToggleOrderEntry.classList.toggle('is-active', active);
        elements.btnToggleOrderEntry.setAttribute('aria-pressed', active ? 'true' : 'false');
        elements.btnToggleOrderEntry.innerHTML = active
            ? '<span class="action-icon">✕</span><span>Menüyü Kapat</span>'
            : '<span class="action-icon">🍽️</span><span>Sipariş Gir</span>';
    }

    const banner = document.getElementById('terminalModeBanner');
    if (banner && isCashier) {
        banner.querySelector('strong').textContent = active ? 'KASİYER SİPARİŞ GİRİŞİ' : 'KASA HESAP TERMİNALİ';
        banner.querySelector('span').textContent = active
            ? 'Menüden ürün eklemek için masa veya paket seçili olmalı'
            : 'Sipariş girişi gerektiğinde Sipariş Gir butonunu kullanın';
    }
}

function setCashierOrderEntry(open) {
    cashierOrderEntryOpen = getTerminalRole() === 'kasa' && !!open;
    renderMenu();
    updateCashierOrderEntryUI();

    if (cashierOrderEntryOpen && !currentMasa) {
        showNotification('Sipariş eklemek için önce masa veya paket seçiniz.', 'info');
    }
}

function toggleCashierOrderEntry() {
    setCashierOrderEntry(!cashierOrderEntryOpen);
}

async function openGunsonuReport() {
    try {
        const response = await fetch('/api/auth/me?path=%2Fgunsonu');
        const data = await response.json();
        if (data.success && data.can_access_path) {
            window.location.href = '/gunsonu';
            return;
        }
        showNotification('Z raporunu sadece yönetici açabilir.', 'warning');
    } catch (error) {
        console.warn('Z raporu yetki kontrolü yapılamadı:', error);
        window.location.href = '/gunsonu';
    }
}

window.openGunsonuReport = openGunsonuReport;

function setupZReportLongPress() {
    const target = elements.companyName;
    if (!target || target.dataset.zReportHoldReady === '1') return;

    target.dataset.zReportHoldReady = '1';
    let holdTimer = null;
    let holdCompleted = false;

    const clearHold = () => {
        if (holdTimer) {
            clearTimeout(holdTimer);
            holdTimer = null;
        }
        target.classList.remove('z-report-hold-active');
    };

    const startHold = (event) => {
        if (event.button !== undefined && event.button !== 0) return;
        holdCompleted = false;
        clearHold();
        target.classList.add('z-report-hold-active');
        holdTimer = setTimeout(() => {
            holdTimer = null;
            holdCompleted = true;
            target.classList.remove('z-report-hold-active');
            openGunsonuReport();
        }, Z_REPORT_HOLD_MS);
    };

    target.addEventListener('pointerdown', startHold);
    target.addEventListener('pointerup', clearHold);
    target.addEventListener('pointercancel', clearHold);
    target.addEventListener('pointerleave', clearHold);
    target.addEventListener('contextmenu', (event) => {
        if (holdTimer || holdCompleted) {
            event.preventDefault();
        }
    });
}

/**
 * Apply restrictions for non-kasa terminals
 */
function applyTerminalRestrictions() {
    console.log('🛡️ Applying terminal restrictions (Checkout disabled)');
    document.body.classList.add('order-terminal');

    // Hide payment buttons
    const paymentButtons = document.querySelector('.payment-buttons');
    if (paymentButtons) paymentButtons.style.display = 'none';

    // Hide management buttons
    const managementToHide = ['btnCari', 'btnSettings', 'btnTerminals', 'btnToggleOrderEntry'];
    managementToHide.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            const link = el.closest('a');
            if (link) link.style.display = 'none';
            else el.style.display = 'none';
        }
    });
    document.querySelectorAll('.main-actions, .management-buttons, .extra-modules').forEach(el => {
        el.style.display = 'none';
    });
    ['btnTransfer', 'btnPrint', 'btnTotalPayment', 'btnToggleOrderEntry'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });

    // Hide split buttons
    if (elements.splitButtonsArea) elements.splitButtonsArea.style.display = 'none';

    // Update terminal text to show it's a terminal
    if (elements.terminalId) {
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
    currentTotal = Number(data.total ?? getPayableTotal(currentItems)) || 0;
    if (Object.prototype.hasOwnProperty.call(data, 'note')) {
        setLocalTableNote(data.masa, data.note);
    }

    updateOrderDisplay();
    updateTableNoteUI();
    updateCourierArea();
    updateQuickSaleUI();
}

function onMasaUpdate(data) {
    console.log('🔄 Masa update:', data);

    // Update adisyonlar
    adisyonlar[data.masa] = data.items || [];
    if (Object.prototype.hasOwnProperty.call(data, 'note')) {
        setLocalTableNote(data.masa, data.note);
    }

    // If this is our current masa, update display
    if (data.masa === currentMasa) {
        currentItems = data.items || [];
        currentTotal = Number(data.total ?? getPayableTotal(currentItems)) || 0;
        updateOrderDisplay();
        updateTableNoteUI();
    }

    // Update table buttons
    updateTableButton(data.masa);
    updateStaffingSummary();
}

function onTableNoteUpdate(data) {
    if (!data || !data.masa) return;
    setLocalTableNote(data.masa, data.note || '');
    updateTableButton(data.masa);
    if (data.masa === currentMasa) {
        updateTableNoteUI({ forceInput: document.activeElement !== elements.tableNoteInput });
    }
}

function onPaymentCompleted(data) {
    console.log('💰 Payment completed:', data);
    resetFinalizePaymentButton();

    // Clear adisyon only when the whole account is closed.
    if (!data.is_partial) {
        adisyonlar[data.masa] = [];
        setLocalTableNote(data.masa, '');
    }

    if (data.masa === currentMasa) {
        // Clear display only when the whole account is closed.
        if (!data.is_partial) {
            currentItems = [];
            currentTotal = 0;
            updateOrderDisplay();
            updateTableNoteUI();
        }
        if (typeof closePaymentModal === 'function') {
            closePaymentModal();
        }
    }

    // Seçimleri temizle
    selectedItemKeys = [];
    updateSplitButtons();

    // Update table button
    updateTableButton(data.masa);
    updateStaffingSummary();
}

function onAdisyonlarUpdate(data) {
    console.log('🔄 Global adisyonlar update:', data);
    adisyonlar = data || {};

    // Update all table buttons
    Object.keys(adisyonlar).forEach(masa => {
        updateTableButton(masa);
    });

    // If we have a selected masa, update its display
    if (currentMasa) {
        currentItems = adisyonlar[currentMasa] || [];
        refreshCurrentTotal();
        updateOrderDisplay();
    }
    updateStaffingSummary();
}

function updateTableNoteUI(options = {}) {
    if (!elements.tableNotePanel || !elements.tableNoteInput) return;
    const hasMasa = !!currentMasa;
    elements.tableNotePanel.style.display = hasMasa ? 'grid' : 'none';
    if (!hasMasa) {
        elements.tableNoteInput.value = '';
        return;
    }

    const shouldUpdateInput = options.forceInput || document.activeElement !== elements.tableNoteInput;
    if (shouldUpdateInput) {
        elements.tableNoteInput.value = getTableNote(currentMasa);
    }
}

function saveCurrentTableNote() {
    if (!currentMasa) {
        showNotification('Lütfen önce masa seçiniz!', 'warning');
        return;
    }
    const note = elements.tableNoteInput ? elements.tableNoteInput.value.trim() : '';
    setLocalTableNote(currentMasa, note);
    updateTableButton(currentMasa);
    socket.emit('set_table_note', {
        masa: currentMasa,
        note
    });
}

function normalizeReservationsPayload(payload) {
    const data = payload && typeof payload === 'object' ? payload : {};
    return {
        success: data.success !== false,
        today: data.today || getLocalDateValue(),
        reservations: Array.isArray(data.reservations) ? data.reservations : [],
        active_by_table: data.active_by_table && typeof data.active_by_table === 'object'
            ? data.active_by_table
            : {},
        active_count: Number(data.active_count || 0),
        today_count: Number(data.today_count || 0)
    };
}

function onReservationsUpdate(data) {
    reservationsPayload = normalizeReservationsPayload(data);
    checkUpcomingReservationAlerts();
}

function parseReservationDateTime(reservation) {
    if (!reservation?.date || !reservation?.time) return null;
    const value = `${reservation.date}T${String(reservation.time).slice(0, 5)}:00`;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
}

function getUpcomingReservationsForAlert() {
    const now = new Date();
    const windowEnd = new Date(now.getTime() + RESERVATION_ALERT_WINDOW_MINUTES * 60000);
    return (reservationsPayload.reservations || [])
        .filter(reservation => reservation.status === 'planlandi')
        .map(reservation => ({ reservation, date: parseReservationDateTime(reservation) }))
        .filter(entry => entry.date && entry.date >= now && entry.date <= windowEnd)
        .sort((a, b) => a.date - b.date)
        .map(entry => entry.reservation);
}

function getReservationAlertKey(reservation) {
    return [
        reservation.id,
        reservation.date,
        reservation.time,
        reservation.masa,
        reservation.guest_count
    ].join('|');
}

function formatReservationAlertMessage(reservation) {
    const parts = [
        reservation.time,
        reservation.masa,
        reservation.customer_name,
        `${Number(reservation.guest_count || 0)} kişi`
    ].filter(Boolean);
    return `Yaklaşan rezervasyon: ${parts.join(' · ')}`;
}

function onReservationMenuNotice(data) {
    if (getTerminalRole() !== 'kasa') return;
    const itemCount = Array.isArray(data?.menu_items) ? data.menu_items.length : 0;
    const panelNames = Array.isArray(data?.panels)
        ? data.panels.map(panel => panel.panel_adi || panel.panel).filter(Boolean).join(', ')
        : '';
    const detail = [
        data?.time,
        data?.masa,
        data?.customer_name,
        itemCount ? `${itemCount} kalem` : '',
        panelNames ? `Reyon: ${panelNames}` : ''
    ].filter(Boolean).join(' · ');
    showNotification(`Rezervasyon menüsü girildi: ${detail}`, 'warning');
}

function checkUpcomingReservationAlerts() {
    const upcoming = getUpcomingReservationsForAlert();
    upcoming.forEach(reservation => {
        const key = getReservationAlertKey(reservation);
        if (alertedReservationKeys.has(key)) return;
        alertedReservationKeys.add(key);
        showNotification(formatReservationAlertMessage(reservation), 'warning');
    });
}

function startReservationAlertPolling() {
    if (reservationAlertTimer) {
        clearInterval(reservationAlertTimer);
    }
    reservationAlertTimer = setInterval(checkUpcomingReservationAlerts, 60000);
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
    const message = (data && data.message) ? String(data.message) : '';
    const normalized = message.toLocaleLowerCase('tr-TR');
    // Payment-completed success toasts are intentionally suppressed.
    if (normalized.includes('ödemesi alındı') || normalized.includes('parçalı ödeme alındı')) {
        resetFinalizePaymentButton();
        if (typeof closePaymentModal === 'function') {
            closePaymentModal();
        }
        refreshCurrentMasaFromServer();
        return;
    }
    showNotification(data.message, 'success');
    if (data && data.type === 'transfer_table' && data.target_masa) {
        selectMasa(data.target_masa);
    }
}

function onVardiyaUpdate(data) {
    console.log('⏳ Vardiya update:', data);
    activeShift = data;
    updateVardiyaUI();
    refreshOperationsStatus({ force: true });
}

function onPortionStockUpdate(data) {
    portionStock = data.portion_stock || {};
    renderMenu();
    updateQuickSaleUI();
}

function onDailyMealsUpdate(data) {
    dailyMeals = data.daily_meals || dailyMeals;
    portionStock = data.portion_stock || portionStock;
    renderMenu();
    updateQuickSaleUI();
}

function getPortionStock(urun) {
    const stockName = getPortionStockName(urun);
    return portionStock[stockName] || portionStock[String(urun || '').trim()] || null;
}

function getPortionStockName(urun) {
    return String(urun || '').trim().replace(/^(tam|yarım|yarim)\s+porsiyon\s+/i, '').trim();
}

function formatPortionAmount(value) {
    const amount = Number(value || 0);
    return Number.isInteger(amount) ? String(amount) : String(amount).replace('.', ',');
}

function normalizeDailyText(value) {
    return String(value || '').trim().toLocaleLowerCase('tr-TR');
}

function getDailyMealCategories() {
    return Array.isArray(dailyMeals.categories) ? dailyMeals.categories : [];
}

function isDailyMealCategory(category) {
    const target = normalizeDailyText(category);
    return !!target && getDailyMealCategories().some(name => normalizeDailyText(name) === target);
}

function getTrackedPortionStock(category, urun) {
    return isDailyMealCategory(category) ? getPortionStock(urun) : null;
}

function canAddPortionItem(urun, category = '') {
    const stock = getTrackedPortionStock(category, urun);
    if (!stock || !stock.tracked) return true;
    const remaining = Number(stock.kalan || 0);
    if (remaining <= 0) {
        showNotification(`${stock.urun || getPortionStockName(urun)} tükendi`, 'warning');
        return false;
    }
    return true;
}

function normalizeQuickSaleText(value) {
    return String(value || '')
        .trim()
        .toLocaleLowerCase('tr-TR')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/ı/g, 'i')
        .replace(/\s+/g, ' ');
}

function getVisibleMenuEntries() {
    const entries = [];
    Object.keys(menuData || {}).forEach(category => {
        (menuData[category] || []).filter(isMenuItemVisible).forEach(item => {
            const name = String(item[0] || '').trim();
            const price = Number(item[1] || 0);
            if (!name || !Number.isFinite(price)) return;
            entries.push({ category, name, price, item });
        });
    });
    return entries;
}

function findQuickWaterItem() {
    const entries = getVisibleMenuEntries();
    return entries.find(entry => {
        const name = normalizeQuickSaleText(entry.name);
        return /\bsu\b/.test(name) && !name.includes('meyve suyu');
    }) || entries.find(entry => {
        const name = normalizeQuickSaleText(entry.name);
        return name.endsWith(' su') || name === 'su';
    });
}

function getWeightedDessertOptions() {
    return getVisibleMenuEntries().filter(entry => {
        const category = normalizeQuickSaleText(entry.category);
        const name = normalizeQuickSaleText(entry.name);
        const looksWeighted = name.includes('kilogram') || name.includes(' kilo') || /\bkg\b/.test(name);
        const looksDessert = category.includes('tatli') || category.includes('baklava') || category.includes('dondurma')
            || name.includes('baklava') || name.includes('dondurma') || name.includes('tatli');
        return looksWeighted && looksDessert;
    });
}

function getSelectedQuickDessert() {
    if (!elements.quickDessertProduct) return null;
    const selectedName = elements.quickDessertProduct.value;
    return getWeightedDessertOptions().find(item => item.name === selectedName) || null;
}

function formatOrderQuantity(value) {
    const quantity = Number(value || 0);
    if (!Number.isFinite(quantity)) return '0';
    if (Number.isInteger(quantity)) return String(quantity);
    return quantity.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
}

function parseOrderQuantity(value, fallback = 1) {
    const quantity = Number(String(value ?? '').replace(',', '.'));
    if (!Number.isFinite(quantity) || quantity <= 0) return fallback;
    return Math.round(quantity * 1000) / 1000;
}

function orderQuantitiesMatch(left, right) {
    return Math.abs(Number(left || 0) - Number(right || 0)) < 0.001;
}

function splitOrderNoteDetails(note) {
    const lines = String(note || '').split(/\r?\n/).map(line => line.trim()).filter(Boolean);
    if (!lines.length || !/^Yemek:\s*/i.test(lines[0])) {
        return { mealName: '', note: String(note || '').trim() };
    }

    return {
        mealName: lines[0].replace(/^Yemek:\s*/i, '').trim(),
        note: lines.slice(1).join('\n')
    };
}

function getOrderPortionLabel(name) {
    const rawName = String(name || '').trim();
    let prefixMatch = rawName.match(/^(tam|yarım|yarim)\s+porsiyon\s+/i);
    if (!prefixMatch) {
        prefixMatch = rawName.match(/^(tam|yarım|yarim)\s+/i);
    }
    if (prefixMatch) {
        return normalizeDailyText(prefixMatch[1]).startsWith('yar') ? 'Yarım Porsiyon' : 'Tam Porsiyon';
    }

    const trailing = rawName.match(/\(\s*(\d+(?:[,.]\d+)?)\s*porsiyon\s*\)\s*$/i);
    if (!trailing) return '';

    const parsed = Number(trailing[1].replace(',', '.'));
    return Number.isFinite(parsed) && parsed > 0 ? `${formatPortionAmount(parsed)} Porsiyon` : '';
}

function getOrderDisplayName(item) {
    const { mealName } = splitOrderNoteDetails(item?.not);
    if (!mealName) return item?.urun || '';

    const portionLabel = getOrderPortionLabel(item?.urun);
    return portionLabel ? `${portionLabel} ${mealName}` : mealName;
}

function getOrderGroupName(item) {
    const parts = [];
    const plateGroup = item?.plate_group;

    if (plateGroup && typeof plateGroup === 'object') {
        const plateLabel = String(plateGroup.label || '').trim();
        const plateId = String(plateGroup.id || '').trim();

        if (plateLabel && plateId) {
            parts.push(`${plateLabel} #${plateId}`);
        } else if (plateLabel) {
            parts.push(plateLabel);
        } else if (plateId) {
            parts.push(`Tabak #${plateId}`);
        }
    }

    const category = String(item?.kategori || item?.category || '').trim();
    if (category) parts.push(category);

    return parts.join(' / ');
}

function getOrderDisplayRows(items = currentItems) {
    const rows = [];

    (items || []).forEach((item, index) => {
        const quantity = parseOrderQuantity(item?.adet, 1);
        if (Number.isInteger(quantity) && quantity > 1) {
            for (let unitNumber = 1; unitNumber <= quantity; unitNumber += 1) {
                rows.push({
                    key: `${index}:${unitNumber}`,
                    item,
                    index,
                    quantity: 1,
                    unitNumber,
                    unitCount: quantity,
                    isSplitUnit: true
                });
            }
            return;
        }

        rows.push({
            key: `${index}:all`,
            item,
            index,
            quantity,
            unitNumber: null,
            unitCount: 1,
            isSplitUnit: false
        });
    });

    return rows;
}

function getSelectedOrderRows() {
    const selectedKeys = new Set(selectedItemKeys);
    return getOrderDisplayRows().filter(row => selectedKeys.has(row.key));
}

function getSelectedPaymentItems() {
    return getSelectedOrderRows().map(row => ({
        ...row.item,
        adet: row.quantity
    }));
}

function getSelectedItemQuantities() {
    const quantitiesByIndex = new Map();

    getSelectedOrderRows().forEach(row => {
        quantitiesByIndex.set(
            row.index,
            (quantitiesByIndex.get(row.index) || 0) + row.quantity
        );
    });

    return Array.from(quantitiesByIndex.entries()).map(([index, quantity]) => ({
        index,
        quantity: parseOrderQuantity(quantity, quantity)
    }));
}

function getSelectedWholeItemIndices() {
    const quantities = getSelectedItemQuantities();
    const indices = [];

    for (const selection of quantities) {
        const item = currentItems[selection.index];
        if (!item) return [];
        if (!orderQuantitiesMatch(selection.quantity, parseOrderQuantity(item.adet, 1))) {
            return [];
        }
        indices.push(selection.index);
    }

    return indices;
}

function pruneSelectedItemKeys() {
    if (!selectedItemKeys.length) return;

    const validKeys = new Set(getOrderDisplayRows().map(row => row.key));
    selectedItemKeys = selectedItemKeys.filter(key => validKeys.has(key));
}

function formatGramAmount(value) {
    const grams = Number(value || 0);
    if (!Number.isFinite(grams)) return '0';
    return Number.isInteger(grams) ? String(grams) : grams.toFixed(1).replace(/0$/, '').replace(/\.$/, '');
}

function populateQuickDessertOptions() {
    if (!elements.quickDessertProduct) return;
    const selected = elements.quickDessertProduct.value;
    const options = getWeightedDessertOptions();
    elements.quickDessertProduct.innerHTML = '';

    if (!options.length) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'Kiloluk tatlı bulunamadı';
        elements.quickDessertProduct.appendChild(option);
        elements.quickDessertProduct.disabled = true;
        if (elements.btnQuickDessertAdd) elements.btnQuickDessertAdd.disabled = true;
        updateQuickDessertPreview();
        return;
    }

    options.forEach(entry => {
        const option = document.createElement('option');
        option.value = entry.name;
        option.textContent = `${entry.name} - ${entry.price.toFixed(2)} TL/kg`;
        elements.quickDessertProduct.appendChild(option);
    });

    if (selected && options.some(entry => entry.name === selected)) {
        elements.quickDessertProduct.value = selected;
    }
    elements.quickDessertProduct.disabled = false;
    if (elements.btnQuickDessertAdd) elements.btnQuickDessertAdd.disabled = !currentMasa;
    updateQuickDessertPreview();
}

function updateQuickSaleUI() {
    if (!elements.cashierQuickSale) return;

    const hasTable = !!currentMasa;
    if (elements.quickSaleMasaHint) {
        elements.quickSaleMasaHint.textContent = hasTable ? currentMasa : 'Masa seçiniz';
    }
    if (elements.btnQuickWater) {
        elements.btnQuickWater.disabled = !hasTable || !findQuickWaterItem();
    }
    if (elements.btnQuickDessert) {
        elements.btnQuickDessert.disabled = !hasTable || getWeightedDessertOptions().length === 0;
    }
    if (elements.btnQuickDessertAdd) {
        elements.btnQuickDessertAdd.disabled = !hasTable || !getSelectedQuickDessert();
    }
    updateQuickDessertPreview();
}

function toggleQuickDessertForm() {
    if (!elements.quickDessertForm) return;
    populateQuickDessertOptions();
    elements.quickDessertForm.classList.toggle('open');
    updateQuickSaleUI();
    if (elements.quickDessertForm.classList.contains('open') && elements.quickDessertGrams) {
        elements.quickDessertGrams.focus();
    }
}

function updateQuickDessertPreview() {
    if (!elements.quickDessertPreview) return;
    const dessert = getSelectedQuickDessert();
    if (!dessert) {
        elements.quickDessertPreview.textContent = 'Kiloluk tatlı bulunamadı';
        return;
    }

    const grams = Number(String(elements.quickDessertGrams?.value || '').replace(',', '.')) || 0;
    if (grams <= 0) {
        elements.quickDessertPreview.textContent = `${dessert.price.toFixed(2)} TL/kg`;
        return;
    }

    const kg = grams / 1000;
    const total = kg * dessert.price;
    elements.quickDessertPreview.textContent = `${formatGramAmount(grams)} gr = ${formatOrderQuantity(kg)} kg / ${total.toFixed(2)} TL`;
}

function addQuickWaterToOrder() {
    const water = findQuickWaterItem();
    if (!water) {
        showNotification('Menüde su ürünü bulunamadı.', 'warning');
        return;
    }
    addItemToOrder(water.name, water.price, {
        allowCashierQuickSale: true,
        category: water.category,
        garson: 'Kasa'
    });
}

function addQuickDessertToOrder() {
    const dessert = getSelectedQuickDessert();
    if (!dessert) {
        showNotification('Kiloluk tatlı seçiniz.', 'warning');
        return;
    }
    const grams = Number(String(elements.quickDessertGrams?.value || '').replace(',', '.')) || 0;
    if (grams <= 0) {
        showNotification('Gram miktarı giriniz.', 'warning');
        return;
    }

    const kg = Math.round((grams / 1000) * 1000) / 1000;
    if (kg <= 0) {
        showNotification('Geçerli bir gram miktarı giriniz.', 'warning');
        return;
    }

    addItemToOrder(dessert.name, dessert.price, {
        allowCashierQuickSale: true,
        adet: kg,
        category: dessert.category,
        garson: 'Kasa',
        not: `${formatGramAmount(grams)} gr`
    });
    if (elements.quickDessertGrams) {
        elements.quickDessertGrams.value = '';
    }
    updateQuickDessertPreview();
}

function updateVardiyaUI() {
    const statusEl = document.getElementById('vardiyaStatus');
    if (!statusEl) return;

    const currentRole = getTerminalRole();
    const isTerminal = (currentRole === 'terminal');

    if (activeShift) {
        console.log('✅ UI: Vardiya Açık', activeShift);
        statusEl.innerHTML = `<span style="color:#2ecc71; font-weight: bold;"><i class="fas fa-clock"></i> ${activeShift.kasiyer} (Açık)</span>`;
        // Enable buttons if they were disabled
        enableCheckoutButtons(true);
    } else {
        console.log('❌ UI: Vardiya Kapalı');
        if (isTerminal) {
            statusEl.innerHTML = ``;
            enableCheckoutButtons(false);
        } else {
            statusEl.innerHTML = `<span style="color:#e74c3c; font-weight: bold;"><i class="fas fa-exclamation-triangle"></i> KASA KAPALI</span>`;
            enableCheckoutButtons(false);
        }
    }
}

function startOperationsStatusPolling() {
    if (!elements.operationsStatusList) return;
    refreshOperationsStatus({ force: true });
    if (operationsStatusTimer) {
        clearInterval(operationsStatusTimer);
    }
    operationsStatusTimer = setInterval(() => refreshOperationsStatus({ force: true }), OPERATIONS_STATUS_REFRESH_MS);
}

async function refreshOperationsStatus(options = {}) {
    if (!elements.operationsStatusList) return;
    if (operationsStatusInFlight) {
        return operationsStatusInFlight;
    }
    const force = options === true || Boolean(options.force);
    const now = Date.now();
    if (!force && now < operationsStatusNextRefreshAt) {
        return;
    }
    operationsStatusNextRefreshAt = now + OPERATIONS_STATUS_MIN_REFRESH_MS;

    operationsStatusInFlight = fetchOperationsStatus();
    try {
        return await operationsStatusInFlight;
    } finally {
        operationsStatusInFlight = null;
    }
}

async function fetchOperationsStatus() {
    if (!elements.operationsStatusList) return;

    const kasaId = getSelectedKasaId();
    const query = Number.isFinite(kasaId) && kasaId > 0
        ? `?kasa_id=${encodeURIComponent(kasaId)}`
        : '';

    try {
        const response = await fetch(`/api/dashboard/status${query}`, { cache: 'no-store' });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();
        renderOperationsStatus(data);
    } catch (error) {
        console.warn('Operasyon durumu alınamadı:', error);
        renderOperationsStatus({
            updated_at: new Date().toISOString(),
            cash_register: { label: 'Kasa', state: activeShift ? 'ok' : 'error', status_text: activeShift ? 'Açık' : 'Kapalı', message: activeShift ? 'Vardiya açık' : 'Vardiya kapalı' },
            okc: { label: 'ÖKC', state: 'warn', status_text: 'Kontrol yok', message: 'Durum alınamadı' },
            printers: []
        });
    }
}

function renderOperationsStatus(data) {
    if (!elements.operationsStatusList) return;

    const cash = data?.cash_register || {};
    const okc = data?.okc || {};
    const printers = Array.isArray(data?.printers) ? data.printers : [];
    const printerChips = printers.map(renderOperationsPrinterChip).join('');

    elements.operationsStatusList.innerHTML = `
        ${renderOperationsStatusRow(cash, 'Kasa')}
        ${renderOperationsStatusRow(okc, 'ÖKC')}
        <div class="operations-printers">
            <div class="operations-printers-title">Yazıcılar</div>
            <div class="operations-printer-grid">
                ${printerChips || '<span class="operations-empty">Yazıcı yok</span>'}
            </div>
        </div>
    `;

    if (elements.operationsStatusUpdated) {
        elements.operationsStatusUpdated.textContent = formatOperationsStatusTime(data?.updated_at);
    }
}

function renderOperationsStatusRow(item, fallbackLabel) {
    const state = normalizeOperationsState(item?.state);
    const label = escapeHtml(item?.label || fallbackLabel);
    const statusText = escapeHtml(item?.status_text || 'Bekleniyor');
    const message = escapeHtml(item?.message || '');
    return `
        <div class="operations-status-row status-${state}">
            <span class="operations-status-dot"></span>
            <div class="operations-status-copy">
                <strong>${label}</strong>
                <span>${message || statusText}</span>
            </div>
            <span class="operations-status-pill">${statusText}</span>
        </div>
    `;
}

function renderOperationsPrinterChip(item) {
    const state = normalizeOperationsState(item?.state);
    const label = escapeHtml(item?.label || 'Yazıcı');
    const statusText = escapeHtml(item?.status_text || 'Bekleniyor');
    const message = escapeHtml(item?.message || statusText);
    return `
        <span class="operations-printer-chip status-${state}" title="${message}">
            <span class="operations-status-dot"></span>
            <strong>${label}</strong>
            <em>${statusText}</em>
        </span>
    `;
}

function normalizeOperationsState(state) {
    return ['ok', 'warn', 'error', 'off'].includes(state) ? state : 'warn';
}

function formatOperationsStatusTime(value) {
    if (!value) return 'Kontrol edildi';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Kontrol edildi';
    return date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}

function enableCheckoutButtons(enabled) {
    const btns = ['btnTotalPayment', 'btnCari', 'btnFinalizePayment'];
    btns.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.disabled = !enabled;
            el.style.opacity = enabled ? '1' : '0.5';
            el.style.cursor = enabled ? 'pointer' : 'not-allowed';
        }
    });

    // Terminal ise zaten kapalı kalmalı
    if (getTerminalRole() === 'terminal') {
        applyTerminalRestrictions();
    }
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
        const role = getTerminalRole();
        elements.terminalId.textContent = role === 'terminal'
            ? `Terminal ${systemInfo.terminal_id} (Sipariş)`
            : `Kasa ${systemInfo.terminal_id}`;
    }

    if (elements.footerTerminal && systemInfo.terminal_id) {
        const role = getTerminalRole();
        elements.footerTerminal.textContent = role === 'terminal'
            ? `🆔 Sipariş Terminali ${systemInfo.terminal_id}`
            : `🆔 Kasa ${systemInfo.terminal_id}`;
    }

    updateVardiyaUI();
    applyRoleProfile(getTerminalRole());
    updateStaffingSummary();
}

function normalizeStaffingName(value) {
    return String(value || '').trim().toLocaleLowerCase('tr-TR');
}

function isIgnoredStaffingWaiter(name) {
    const normalized = normalizeStaffingName(name);
    return !normalized
        || STAFFING_IGNORED_WAITER_NAMES.has(normalized)
        || normalized.startsWith('terminal ');
}

function addStaffingWaiterName(waiterMap, name) {
    const cleanName = String(name || '').trim();
    if (isIgnoredStaffingWaiter(cleanName)) return;
    waiterMap.set(normalizeStaffingName(cleanName), cleanName);
}

function getSalonTableNames() {
    const salons = Array.isArray(systemInfo.salons) ? systemInfo.salons : [];
    const tableNames = [];

    if (salons.length > 0) {
        salons.forEach(salon => {
            (salon.tables || []).forEach(table => {
                const name = String(table || '').trim();
                if (name) tableNames.push(name);
            });
        });
        return tableNames;
    }

    const masaCount = Number(systemInfo.masa_sayisi || 0);
    for (let i = 1; i <= masaCount; i++) {
        tableNames.push(`Masa ${i}`);
    }
    return tableNames;
}

function getActiveSalonTableNames(tableNames) {
    return (tableNames || []).filter(tableName => {
        const items = adisyonlar[tableName] || [];
        return Array.isArray(items) && items.length > 0;
    });
}

function getActiveWaiterNamesForStaffing(activeTableNames) {
    const waiterMap = new Map();
    if (Array.isArray(systemInfo.active_waiters)) {
        systemInfo.active_waiters.forEach(name => addStaffingWaiterName(waiterMap, name));
    }

    (activeTableNames || []).forEach(tableName => {
        const items = adisyonlar[tableName] || [];
        items.forEach(item => {
            addStaffingWaiterName(waiterMap, item?.garson);
            addStaffingWaiterName(waiterMap, item?.servis_garson);
        });
    });

    return Array.from(waiterMap.values()).sort((a, b) => a.localeCompare(b, 'tr-TR'));
}

function getStaffingLoadSnapshot() {
    const tableNames = getSalonTableNames();
    const activeTableNames = getActiveSalonTableNames(tableNames);
    const activeWaiterNames = getActiveWaiterNamesForStaffing(activeTableNames);
    const connectedWaiterCount = Number(systemInfo.active_waiter_count || 0) || 0;
    const activeTables = activeTableNames.length;
    const totalTables = tableNames.length;
    const requiredWaiters = activeTables > 0
        ? Math.max(1, Math.ceil(activeTables / STAFF_TABLES_PER_WAITER))
        : 0;
    const activeWaiterCount = Math.max(activeWaiterNames.length, connectedWaiterCount);

    return {
        activeTables,
        totalTables,
        occupancy: totalTables > 0 ? Math.round((activeTables / totalTables) * 100) : 0,
        activeWaiterCount,
        activeWaiterNames,
        requiredWaiters,
        deficit: Math.max(0, requiredWaiters - activeWaiterCount)
    };
}

function getStaffingRecommendation(snapshot) {
    if (snapshot.totalTables === 0) {
        return {
            level: 'idle',
            title: 'Salon masası tanımlı değil',
            detail: 'Ayarlar ekranından salon veya masa sayısı eklenmeli.'
        };
    }

    if (snapshot.activeTables === 0) {
        return {
            level: 'idle',
            title: 'Yoğunluk yok',
            detail: 'Aktif salon masası bulunmuyor.'
        };
    }

    if (snapshot.deficit > 0) {
        return {
            level: snapshot.deficit >= 2 || snapshot.occupancy >= 70 ? 'critical' : 'warning',
            title: `${snapshot.deficit} garson takviyesi önerilir`,
            detail: `${snapshot.activeTables} aktif masa için en az ${snapshot.requiredWaiters} garson gerekir.`
        };
    }

    if (snapshot.occupancy >= 85) {
        return {
            level: 'warning',
            title: 'Salon çok yoğun',
            detail: 'Mevcut ekip yeterli görünüyor, takviye hazırda bekletilmeli.'
        };
    }

    if (snapshot.occupancy >= 60) {
        return {
            level: 'busy',
            title: 'Yoğunluk yükseliyor',
            detail: 'Takviye gerekmiyor, servis temposu takip edilmeli.'
        };
    }

    return {
        level: 'ok',
        title: 'Takviye gerekmiyor',
        detail: 'Mevcut ekip aktif masa yükünü karşılıyor.'
    };
}

function updateStaffingSummary() {
    if (!elements.staffingSummary) return;

    const snapshot = getStaffingLoadSnapshot();
    const recommendation = getStaffingRecommendation(snapshot);
    const classNames = [
        'staffing-idle',
        'staffing-ok',
        'staffing-busy',
        'staffing-warning',
        'staffing-critical'
    ];
    const waiterNames = snapshot.activeWaiterNames;
    const waiterText = waiterNames.length
        ? `Aktif: ${waiterNames.slice(0, 3).join(', ')}${waiterNames.length > 3 ? '...' : ''}`
        : (
            snapshot.activeWaiterCount > 0
                ? `${snapshot.activeWaiterCount} aktif garson`
                : (snapshot.activeTables > 0 ? 'Aktif garson oturumu görünmüyor' : '')
        );

    elements.staffingSummary.classList.remove(...classNames);
    elements.staffingSummary.classList.add(`staffing-${recommendation.level}`);

    if (elements.staffingRecommendation) {
        elements.staffingRecommendation.textContent = recommendation.title;
    }
    if (elements.staffingDetail) {
        elements.staffingDetail.textContent = waiterText
            ? `${recommendation.detail} ${waiterText}.`
            : recommendation.detail;
    }
    if (elements.staffingActiveTables) {
        elements.staffingActiveTables.textContent = `${snapshot.activeTables}/${snapshot.totalTables}`;
    }
    if (elements.staffingOccupancy) {
        elements.staffingOccupancy.textContent = `${snapshot.occupancy}%`;
    }
    if (elements.staffingActiveWaiters) {
        elements.staffingActiveWaiters.textContent = snapshot.activeWaiterCount;
        elements.staffingActiveWaiters.parentElement.title = waiterNames.length
            ? `Aktif garsonlar: ${waiterNames.join(', ')}`
            : 'Aktif garson oturumu görünmüyor';
    }
    if (elements.staffingNeededWaiters) {
        elements.staffingNeededWaiters.textContent = snapshot.requiredWaiters;
    }
    if (elements.staffingStatusDot) {
        elements.staffingStatusDot.title = recommendation.title;
    }
}

function renderMenu() {
    if (!elements.menuContainer) return;

    elements.menuContainer.innerHTML = '';
    populateQuickDessertOptions();
    if (!canEnterOrders()) {
        updateQuickSaleUI();
        return;
    }

    Object.keys(menuData).forEach((category, index) => {
        const visibleItems = (menuData[category] || []).filter(isMenuItemVisible);
        if (!visibleItems.length) return;

        const categoryDiv = document.createElement('div');
        categoryDiv.className = 'menu-category';

        const categoryTitle = document.createElement('div');
        categoryTitle.className = 'category-title';
        categoryTitle.textContent = category;
        categoryTitle.style.background = getCategoryColor(index);
        categoryDiv.appendChild(categoryTitle);

        const itemsDiv = document.createElement('div');
        itemsDiv.className = 'menu-items';

        visibleItems.forEach(item => {
            const [name, price] = item;
            const stock = getTrackedPortionStock(category, name);
            const tracked = !!(stock && stock.tracked);
            const remaining = tracked ? Number(stock.kalan || 0) : null;
            const soldOut = tracked && remaining <= 0;
            const itemBtn = document.createElement('button');
            itemBtn.className = 'menu-item' + (soldOut ? ' sold-out' : (tracked && remaining <= 5 ? ' low-stock' : ''));
            itemBtn.style.background = `linear-gradient(135deg, ${getCategoryColor(index)}, ${darkenColor(getCategoryColor(index))})`;

            itemBtn.innerHTML = `
                <span class="item-name">${escapeHtml(name)}${tracked ? `<span class="item-stock">${soldOut ? 'Tükendi' : 'Kalan: ' + formatPortionAmount(remaining)}</span>` : ''}</span>
                <span class="item-price">${price.toFixed(2)} TL</span>
            `;

            itemBtn.onclick = () => {
                if (soldOut) {
                    showNotification(`${stock.urun || getPortionStockName(name)} tükendi`, 'warning');
                    return;
                }
                addItemToOrder(name, price, {
                    category,
                    garson: getTerminalRole() === 'kasa' ? 'Kasa' : undefined
                });
            };
            itemsDiv.appendChild(itemBtn);
        });

        categoryDiv.appendChild(itemsDiv);
        elements.menuContainer.appendChild(categoryDiv);
    });
    updateQuickSaleUI();
}

function renderTables() {
    if (!elements.paketSection || !elements.paketGrid || !elements.masaSection) return;

    const paketLabels = getPaketLabels();
    const masaCount = Number(systemInfo.masa_sayisi || 0);
    const salons = Array.isArray(systemInfo.salons) ? systemInfo.salons : [];

    // Paket section
    if (paketLabels.length > 0) {
        elements.paketSection.style.display = 'block';
        elements.paketGrid.innerHTML = '';

        paketLabels.forEach(masa => {
            const btn = createTableButton(masa, true);
            elements.paketGrid.appendChild(btn);
        });
    } else {
        elements.paketSection.style.display = 'none';
        elements.paketGrid.innerHTML = '';
    }

    // Salon section (Grouped or Flat)
    elements.masaSection.innerHTML = '';

    if (salons.length > 0) {
        elements.masaSection.style.display = 'block';

        salons.forEach(salon => {
            const title = document.createElement('h3');
            title.className = 'section-title';
            title.textContent = `🪑 ${salon.name}`;
            elements.masaSection.appendChild(title);

            const grid = document.createElement('div');
            grid.className = 'tables-grid';

            (salon.tables || []).forEach(table => {
                const btn = createTableButton(table, false);
                grid.appendChild(btn);
            });

            elements.masaSection.appendChild(grid);
        });
    } else if (masaCount > 0) {
        elements.masaSection.style.display = 'block';

        const title = document.createElement('h3');
        title.className = 'section-title';
        title.textContent = '🪑 Salon';
        elements.masaSection.appendChild(title);

        const grid = document.createElement('div');
        grid.className = 'tables-grid';
        grid.id = 'masaGrid';
        elements.masaGrid = grid;
        elements.masaSection.appendChild(grid);

        for (let i = 1; i <= masaCount; i++) {
            const masa = `Masa ${i}`;
            const btn = createTableButton(masa, false);
            grid.appendChild(btn);
        }
    } else {
        elements.masaSection.style.display = 'none';
    }

    updateStaffingSummary();
}

function getTableButtonContent(masa, items) {
    const safeMasa = escapeHtml(masa);
    const noteBadge = getTableNote(masa)
        ? '<span class="table-note-badge">NOT</span>'
        : '';
    if ((items || []).length > 0) {
        const total = getPayableTotal(items);
        const ikramTotal = getComplimentaryTotal(items);
        return `<div>${safeMasa}</div><div>${total.toFixed(2)} TL</div>${ikramTotal > 0 ? `<small>İkram ${ikramTotal.toFixed(2)}</small>` : ''}${noteBadge}`;
    }
    return `<div>${safeMasa}</div>${noteBadge}`;
}

function createTableButton(masa, isPaket) {
    const btn = document.createElement('button');
    btn.className = 'table-btn';
    btn.id = getTableButtonId(masa);

    if (isPaket) {
        btn.classList.add('paket');
    }

    const items = adisyonlar[masa] || [];
    btn.classList.toggle('has-note', !!getTableNote(masa));

    if (items.length > 0) {
        btn.classList.add('occupied');
        btn.innerHTML = getTableButtonContent(masa, items);
    } else {
        btn.innerHTML = getTableButtonContent(masa, items);
    }

    btn.onclick = () => selectMasa(masa);

    return btn;
}

function createTablePickerButton(masa, isPaket) {
    const btn = document.createElement('button');
    btn.className = 'table-btn table-picker-btn';
    btn.type = 'button';

    if (isPaket) {
        btn.classList.add('paket');
    }

    const items = adisyonlar[masa] || [];
    btn.classList.toggle('occupied', items.length > 0);
    btn.classList.toggle('selected', masa === currentMasa);
    btn.classList.toggle('has-note', !!getTableNote(masa));
    btn.innerHTML = getTableButtonContent(masa, items);
    btn.onclick = () => {
        selectMasa(masa);
        closeTablePickerModal();
    };

    return btn;
}

function appendTablePickerGroup(titleText, tables, isPaket = false) {
    if (!elements.tablePickerGrid || !Array.isArray(tables) || tables.length === 0) return;

    const group = document.createElement('section');
    group.className = 'table-picker-group';

    const title = document.createElement('h3');
    title.className = 'table-picker-title';
    title.textContent = titleText;
    group.appendChild(title);

    const grid = document.createElement('div');
    grid.className = 'tables-grid table-picker-grid';
    tables.forEach(masa => {
        grid.appendChild(createTablePickerButton(masa, isPaket));
    });
    group.appendChild(grid);

    elements.tablePickerGrid.appendChild(group);
}

function renderTablePicker() {
    if (!elements.tablePickerGrid) return;

    elements.tablePickerGrid.innerHTML = '';

    const paketLabels = getPaketLabels();
    if (paketLabels.length > 0) {
        appendTablePickerGroup('Paket Servis', paketLabels, true);
    }

    const salons = Array.isArray(systemInfo.salons) ? systemInfo.salons : [];
    if (salons.length > 0) {
        salons.forEach(salon => {
            appendTablePickerGroup(salon.name || 'Salon', salon.tables || [], false);
        });
    } else {
        const masaCount = Number(systemInfo.masa_sayisi || 0);
        if (masaCount > 0) {
            const tables = Array.from({ length: masaCount }, (_, index) => `Masa ${index + 1}`);
            appendTablePickerGroup('Salon', tables, false);
        }
    }

    if (!elements.tablePickerGrid.children.length) {
        const empty = document.createElement('div');
        empty.className = 'table-picker-empty';
        empty.textContent = 'Masa tanımı bulunamadı';
        elements.tablePickerGrid.appendChild(empty);
    }
}

function openTablePickerModal() {
    renderTablePicker();
    if (elements.tablePickerModal) {
        elements.tablePickerModal.style.display = 'block';
    }
}

function closeTablePickerModal() {
    if (elements.tablePickerModal) {
        elements.tablePickerModal.style.display = 'none';
    }
}

function getLocalDateValue(date = new Date()) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function updateTableButton(masa) {
    const btnId = getTableButtonId(masa);
    const btn = document.getElementById(btnId);

    if (!btn) return;

    const items = adisyonlar[masa] || [];
    btn.classList.toggle('has-note', !!getTableNote(masa));

    if (items.length > 0) {
        btn.classList.add('occupied');
        btn.innerHTML = getTableButtonContent(masa, items);
    } else {
        btn.classList.remove('occupied');
        btn.innerHTML = getTableButtonContent(masa, items);
    }
}

function selectMasa(masa) {
    currentMasa = masa;

    // Update selection visual
    document.querySelectorAll('.table-btn').forEach(btn => {
        btn.classList.remove('selected');
    });

    const btnId = getTableButtonId(masa);
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
    updateTableNoteUI();

    // Reset selection on masa switch
    selectedItemKeys = [];
    updateSplitButtons();
    updateQuickSaleUI();
}

function updateOrderDisplay() {
    if (!elements.orderList) return;

    refreshCurrentTotal();
    pruneSelectedItemKeys();

    if (currentItems.length === 0) {
        elements.orderList.innerHTML = '<div class="empty-state"><p>Sipariş yok</p></div>';
    } else {
        elements.orderList.innerHTML = '';

        getOrderDisplayRows().forEach((row) => {
            const item = row.item;
            const orderItem = document.createElement('div');
            orderItem.className = 'order-item';
            if (row.isSplitUnit) {
                orderItem.classList.add('split-unit');
            }

            const displayItem = { ...item, adet: row.quantity };
            const listTotal = getLineTotal(displayItem);
            const isIkram = isComplimentaryItem(item);
            const itemTotal = isIkram ? 0 : listTotal;
            const isHazir = isReadyItem(item);
            const isServed = isServedItem(item);
            const statusBadge = isHazir
                ? '<span style="color: #2ecc71; font-weight: bold; font-size: 10px;">[HAZIR] </span>'
                : (isServed ? '<span style="color: #7f8c8d; font-weight: bold; font-size: 10px;">[SERVİS EDİLDİ] </span>' : '');
            const displayName = getOrderDisplayName(item);
            const itemNote = splitOrderNoteDetails(item.not).note;
            const groupName = getOrderGroupName(item);
            const unitChip = row.isSplitUnit
                ? `<span class="order-unit-chip">${row.unitNumber}/${row.unitCount}</span>`
                : '';
            const canCancelFromRow = isKitchenCancelableItem(item)
                && item.uid
                && (!row.isSplitUnit || row.unitNumber === 1);
            const cancelTitle = row.isSplitUnit
                ? 'Bu ürün satırının tamamını iptal eder'
                : 'Siparişi iptal et';

            if (isIkram) {
                orderItem.classList.add('ikram');
            }

            orderItem.innerHTML = `
                <div class="order-item-info">
                    ${groupName ? `<div class="order-item-group">${escapeHtml(groupName)}</div>` : ''}
                    <div class="order-item-name">
                        ${statusBadge}
                        ${formatOrderQuantity(row.quantity)}x ${escapeHtml(displayName)}${unitChip}${isIkram ? ' (İKRAM)' : ''}
                    </div>
                    <div class="order-item-meta">${escapeHtml(item.garson || 'Bilinmiyor')} - ${escapeHtml(item.saat || '')}</div>
                    ${itemNote ? `<div class="order-item-note">Not: ${escapeHtml(itemNote)}</div>` : ''}
                </div>
                <div class="order-item-actions">
                    <div class="order-item-price">${isIkram ? `İKRAM<br><small>${listTotal.toFixed(2)} TL</small>` : `${itemTotal.toFixed(2)} TL`}</div>
                    ${canCancelFromRow ? `
                        <button class="btn-cancel-small" onclick="cancelItem('${item.uid}', event)"
                                title="${escapeHtml(cancelTitle)}"
                                style="background: #e74c3c; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-size: 10px; cursor: pointer;">
                            İPTAL
                        </button>
                    ` : ''}
                </div>
            `;

            if (selectedItemKeys.includes(row.key)) {
                orderItem.classList.add('selected');
            }

            orderItem.onclick = (e) => {
                if (!e.target.closest('button')) {
                    toggleItemSelection(row.key);
                }
            };

            elements.orderList.appendChild(orderItem);
        });
    }

    // Update total
    if (elements.totalAmount) {
        elements.totalAmount.textContent = `${currentTotal.toFixed(2)} TL`;
    }
    if (elements.complimentaryAmount) {
        const ikramTotal = getComplimentaryTotal();
        elements.complimentaryAmount.textContent = ikramTotal > 0 ? `İkram: ${ikramTotal.toFixed(2)} TL` : '';
    }
    updateComplimentaryCloseButton();
}

/**
 * Order management
 */
function addItemToOrder(urun, fiyat, options = {}) {
    const allowCashierQuickSale = options.allowCashierQuickSale === true;
    if (!canEnterOrders() && !allowCashierQuickSale) {
        showNotification('Kasada sipariş girişi kapalı. Siparişleri garson ekranından girin.', 'warning');
        return;
    }
    if (!currentMasa) {
        showNotification('Lütfen önce masa seçiniz!', 'warning');
        return;
    }
    if (!canAddPortionItem(urun, options.category || '')) {
        return;
    }

    const quantity = Number(options.adet || 1);
    if (!Number.isFinite(quantity) || quantity <= 0) {
        showNotification('Geçerli miktar giriniz.', 'warning');
        return;
    }

    socket.emit('add_item', {
        masa: currentMasa,
        urun: urun,
        fiyat: fiyat,
        adet: quantity,
        kategori: options.category || '',
        garson: options.garson || 'Bilinmiyor',
        not: options.not || '',
        source: allowCashierQuickSale ? 'cashier_quick_sale' : 'menu'
    });
}

function removeItemFromOrder(index) {
    socket.emit('remove_item', { index: index });
}

/**
 * Table Transfer logic
 */
function openTransferModal() {
    if (!currentMasa || currentItems.length === 0) {
        showNotification('Taşınacak aktif bir sipariş bulunmuyor!', 'warning');
        return;
    }

    elements.transferTargetGrid.innerHTML = '';

    // Render all available tables in the modal
    // Salons
    if (systemInfo.salons && systemInfo.salons.length > 0) {
        systemInfo.salons.forEach(salon => {
            const groupHeader = document.createElement('div');
            groupHeader.style.gridColumn = '1 / -1';
            groupHeader.style.padding = '10px';
            groupHeader.style.fontWeight = 'bold';
            groupHeader.style.borderBottom = '1px solid #eee';
            groupHeader.textContent = salon.name;
            elements.transferTargetGrid.appendChild(groupHeader);

            salon.tables.forEach(table => {
                if (table === currentMasa) return; // Skip current
                const btn = document.createElement('button');
                btn.className = 'table-btn';
                btn.style.minHeight = '60px';
                btn.textContent = table;
                btn.onclick = () => confirmTransfer(table);
                elements.transferTargetGrid.appendChild(btn);
            });
        });
    } else {
        // Flat tables
        for (let i = 1; i <= systemInfo.masa_sayisi; i++) {
            const table = `Masa ${i}`;
            if (table === currentMasa) continue;
            const btn = document.createElement('button');
            btn.className = 'table-btn';
            btn.style.minHeight = '60px';
            btn.textContent = table;
            btn.onclick = () => confirmTransfer(table);
            elements.transferTargetGrid.appendChild(btn);
        }
    }

    elements.transferModal.style.display = 'block';
}

function confirmTransfer(targetMasa) {
    if (!confirm(`${currentMasa} masasını ${targetMasa} masasına taşımak istediğinize emin misiniz?`)) {
        return;
    }

    socket.emit('transfer_table', {
        source_masa: currentMasa,
        target_masa: targetMasa
    });

    closeTransferModal();
}

function closeTransferModal() {
    elements.transferModal.style.display = 'none';
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

/**
 * Split Payment Modal Functions
 */
function moneyToCents(value) {
    const parsed = parseFloat(value);
    if (!Number.isFinite(parsed)) return 0;
    return Math.max(0, Math.round(parsed * 100));
}

function centsToMoney(cents) {
    return Math.max(0, cents) / 100;
}

function formatMoneyValue(value) {
    return centsToMoney(moneyToCents(value)).toFixed(2);
}

function setMoneyInputValue(input, amount) {
    if (!input) return;
    const cents = moneyToCents(amount);
    input.value = cents > 0 ? centsToMoney(cents).toFixed(2) : '';
}

function splitAmountEvenly(amount, count) {
    const totalCents = moneyToCents(amount);
    const splitCount = Math.max(1, parseInt(count, 10) || 1);
    const base = Math.floor(totalCents / splitCount);
    let remainder = totalCents % splitCount;

    return Array.from({ length: splitCount }, () => {
        const cents = base + (remainder > 0 ? 1 : 0);
        if (remainder > 0) remainder -= 1;
        return centsToMoney(cents);
    });
}

function getCardSplitInputs() {
    if (!elements.cardSplitRows) return [];
    return Array.from(elements.cardSplitRows.querySelectorAll('.card-split-amount'));
}

function getCardSplitAmounts() {
    return getCardSplitInputs().map(input => centsToMoney(moneyToCents(input.value)));
}

function getCardSplitTotal() {
    return getCardSplitAmounts().reduce((sum, amount) => sum + amount, 0);
}

function updateCardSplitPanel() {
    if (!elements.cardSplitPanel) return;

    const kart = moneyToCents(elements.paymentKart?.value || 0);
    const rows = getCardSplitInputs();
    const hasCardPayment = kart > 0 || rows.length > 0;

    elements.cardSplitPanel.style.display = hasCardPayment ? 'block' : 'none';
    if (elements.cardSplitSummary) {
        const rowCount = Math.max(rows.length, kart > 0 ? 1 : 0);
        const total = centsToMoney(kart).toFixed(2);
        elements.cardSplitSummary.textContent = rowCount > 1 ? `${rowCount} kart | ${total} TL` : `1 kart | ${total} TL`;
    }

    rows.forEach((input, index) => {
        const row = input.closest('.card-split-row');
        const label = row?.querySelector('.card-split-label');
        const removeBtn = row?.querySelector('.card-split-remove');
        if (label) label.textContent = `Kart ${index + 1}`;
        if (removeBtn) removeBtn.disabled = rows.length <= 1;
    });
}

function renderCardSplitRows(amounts = [], focusIndex = null) {
    if (!elements.cardSplitRows) return;

    elements.cardSplitRows.innerHTML = '';
    amounts.forEach((amount, index) => {
        const row = document.createElement('div');
        row.className = 'card-split-row';

        const label = document.createElement('span');
        label.className = 'card-split-label';
        label.textContent = `Kart ${index + 1}`;

        const input = document.createElement('input');
        input.type = 'number';
        input.step = '0.01';
        input.min = '0';
        input.className = 'card-split-amount';
        input.value = formatMoneyValue(amount);
        input.addEventListener('input', () => {
            syncCardTotalFromSplitRows();
            balancePaymentInputs(elements.paymentKart);
        });
        input.addEventListener('focus', () => input.select());

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'card-split-remove';
        removeBtn.textContent = '×';
        removeBtn.addEventListener('click', () => removeCardSplitRow(index));

        row.appendChild(label);
        row.appendChild(input);
        row.appendChild(removeBtn);
        elements.cardSplitRows.appendChild(row);
    });

    updateCardSplitPanel();

    if (focusIndex !== null) {
        const inputs = getCardSplitInputs();
        const target = inputs[Math.max(0, Math.min(focusIndex, inputs.length - 1))];
        if (target) {
            target.focus();
            target.select();
        }
    }
}

function syncCardTotalFromSplitRows() {
    if (suppressCardSplitSync) return;
    suppressCardSplitSync = true;
    setMoneyInputValue(elements.paymentKart, getCardSplitTotal());
    suppressCardSplitSync = false;
    updateCardSplitPanel();
}

function syncCardSplitRowsToTotal() {
    if (suppressCardSplitSync || !elements.cardSplitRows) return;

    const totalCents = moneyToCents(elements.paymentKart?.value || 0);
    const amounts = getCardSplitAmounts();

    if (totalCents <= 0) {
        renderCardSplitRows([]);
        return;
    }

    if (amounts.length <= 1) {
        renderCardSplitRows([centsToMoney(totalCents)]);
        return;
    }

    const currentCents = amounts.map(moneyToCents);
    const currentTotal = currentCents.reduce((sum, cents) => sum + cents, 0);
    const delta = totalCents - currentTotal;
    const nextCents = [...currentCents];
    nextCents[nextCents.length - 1] += delta;

    if (nextCents.some(cents => cents < 0)) {
        renderCardSplitRows(splitAmountEvenly(centsToMoney(totalCents), amounts.length));
        return;
    }

    renderCardSplitRows(nextCents.map(centsToMoney));
}

function addCardSplitRow() {
    const total = centsToMoney(moneyToCents(elements.paymentKart?.value || 0));
    if (total <= 0) {
        showNotification('Önce kart tutarı giriniz.', 'warning');
        return;
    }

    const amounts = getCardSplitAmounts();
    if (amounts.length <= 1) {
        renderCardSplitRows(splitAmountEvenly(total, 2), 1);
        syncCardTotalFromSplitRows();
        return;
    }

    const rowTotalCents = amounts.map(moneyToCents).reduce((sum, cents) => sum + cents, 0);
    const remainingCents = Math.max(0, moneyToCents(total) - rowTotalCents);
    renderCardSplitRows([...amounts, centsToMoney(remainingCents)], amounts.length);
    syncCardTotalFromSplitRows();
}

function splitCardsEqual() {
    const total = centsToMoney(moneyToCents(elements.paymentKart?.value || 0));
    if (total <= 0) {
        showNotification('Önce kart tutarı giriniz.', 'warning');
        return;
    }

    const count = Math.max(2, getCardSplitInputs().length || 2);
    renderCardSplitRows(splitAmountEvenly(total, count));
    syncCardTotalFromSplitRows();
}

function removeCardSplitRow(index) {
    const amounts = getCardSplitAmounts();
    if (amounts.length <= 1) return;

    amounts.splice(index, 1);
    renderCardSplitRows(amounts);
    syncCardTotalFromSplitRows();
    balancePaymentInputs(elements.paymentKart);
}

function getCardPaymentParts() {
    const splitAmounts = getCardSplitAmounts().filter(amount => moneyToCents(amount) > 0);
    if (splitAmounts.length > 0) return splitAmounts;

    const kart = centsToMoney(moneyToCents(elements.paymentKart?.value || 0));
    return kart > 0 ? [kart] : [];
}

function checkVardiya() {
    const isTerminal = getTerminalRole() === 'terminal';
    if (isTerminal) return true; // Terminal restricts checkout via UI anyway

    if (!activeShift) {
        if (confirm("Kasa açık değil! Vardiya başlatmak için Kasa Yönetimi sayfasına gitmek ister misiniz?")) {
            window.location.href = 'kasa_yonetimi.html';
        }
        return false;
    }
    return true;
}

function toggleItemSelection(key) {
    const pos = selectedItemKeys.indexOf(key);
    if (pos === -1) {
        selectedItemKeys.push(key);
    } else {
        selectedItemKeys.splice(pos, 1);
    }
    updateOrderDisplay();
    updateSplitButtons();
}

function updateSplitButtons() {
    updateComplimentaryCloseButton();
    if (!elements.splitButtonsArea) return;

    if (selectedItemKeys.length > 0) {
        const selectedItems = getSelectedPaymentItems();
        const selectedPayable = getPayableTotal(selectedItems);
        const hasNormal = selectedItems.some(item => !isComplimentaryItem(item));
        const hasIkram = selectedItems.some(isComplimentaryItem);
        const wholeItemIndices = getSelectedWholeItemIndices();
        const canChangeComplimentary = wholeItemIndices.length > 0;

        elements.splitButtonsArea.style.display = 'block';
        elements.selectedCount.textContent = selectedItemKeys.length;
        if (elements.btnPaySelected) {
            elements.btnPaySelected.style.display = selectedPayable > 0 ? 'block' : 'none';
        }
        if (elements.btnCompSelected) {
            elements.btnCompSelected.style.display = hasNormal && canChangeComplimentary ? 'block' : 'none';
        }
        if (elements.btnUncompSelected) {
            elements.btnUncompSelected.style.display = hasIkram && canChangeComplimentary ? 'block' : 'none';
        }
    } else {
        elements.splitButtonsArea.style.display = 'none';
    }
}

function updateComplimentaryCloseButton() {
    if (!elements.btnCloseCompBill) return;

    const canCloseAsComp = currentItems.length > 0 && currentTotal <= 0.01 && getComplimentaryTotal() > 0;
    elements.btnCloseCompBill.style.display = canCloseAsComp ? 'block' : 'none';
}

function setSelectedComplimentary(ikram) {
    if (!currentMasa) {
        showNotification('Lütfen önce masa seçiniz!', 'warning');
        return;
    }
    if (selectedItemKeys.length === 0) {
        showNotification('Lütfen ürün seçiniz!', 'warning');
        return;
    }
    const selectedWholeItemIndices = getSelectedWholeItemIndices();
    if (!selectedWholeItemIndices.length) {
        showNotification('İkram işlemi için ürün satırının tamamını seçiniz.', 'warning');
        return;
    }

    const currentRole = getTerminalRole();
    if (currentRole === 'terminal') {
        showNotification('Bu terminal yetkili değildir!', 'error');
        return;
    }

    socket.emit('set_item_comp', {
        masa: currentMasa,
        item_indices: selectedWholeItemIndices,
        ikram,
        role: currentRole
    });

    selectedItemKeys = [];
    updateOrderDisplay();
    updateSplitButtons();
}

function closeComplimentaryBill() {
    if (!currentMasa) {
        showNotification('Lütfen önce masa seçiniz!', 'warning');
        return;
    }
    if (!checkVardiya()) return;
    if (currentItems.length === 0) {
        showNotification('Sipariş listesi boş!', 'warning');
        return;
    }
    if (currentTotal > 0.01) {
        showNotification('Ücretli ürünler var. Önce tahsil edin veya ikram olarak işaretleyin.', 'warning');
        return;
    }

    const ikramTotal = getComplimentaryTotal();
    if (!confirm(`Bu hesap ${ikramTotal.toFixed(2)} TL ikram olarak kapatılacak. Onaylıyor musunuz?`)) {
        return;
    }

    const currentRole = getTerminalRole();
    socket.emit('close_complimentary_bill', {
        masa: currentMasa,
        role: currentRole
    });
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
        return getPayableTotal(getSelectedPaymentItems());
    }
    return currentTotal;
}

function openPaymentModal(prefillType = null, isSelective = false) {
    if (paymentInProgress) {
        showNotification('ÖKC işlemi devam ediyor, lütfen tamamlanmasını bekleyin.', 'info');
        return;
    }

    if (!currentMasa) {
        showNotification('Lütfen önce masa seçiniz!', 'warning');
        return;
    }

    if (!checkVardiya()) return;

    const itemsToPay = isSelective ? getSelectedPaymentItems() : currentItems;

    if (itemsToPay.length === 0) {
        showNotification('Sipariş listesi boş!', 'warning');
        return;
    }

    isSelectivePayment = isSelective;
    const itemsTotal = getPayableTotal(itemsToPay);

    if (itemsTotal <= 0) {
        showNotification('Seçimde tahsil edilecek ürün yok. İkram hesabı kapatmak için İkram Kapat kullanın.', 'warning');
        return;
    }

    const selectedPaymentMethod = normalizePaymentMethod(prefillType || getDefaultPaymentMethod());

    // Reset inputs
    elements.paymentNakit.value = '';
    elements.paymentKart.value = '';
    elements.paymentCari.value = '';

    // Pre-fill using the selected/default payment method
    if (selectedPaymentMethod === 'Nakit') elements.paymentNakit.value = itemsTotal.toFixed(2);
    if (selectedPaymentMethod === 'Kredi Kartı') elements.paymentKart.value = itemsTotal.toFixed(2);
    if (selectedPaymentMethod === 'Açık Hesap') elements.paymentCari.value = itemsTotal.toFixed(2);
    syncCardSplitRowsToTotal();

    elements.customerSearch.value = '';
    elements.selectedCustomer.value = '';
    elements.selectedCustomerDisplay.textContent = 'Henüz müşteri seçilmedi';
    elements.customerSelectionDiv.style.display = selectedPaymentMethod === 'Açık Hesap' ? 'block' : 'none';
    if (elements.invoicePending) {
        elements.invoicePending.checked = false;
    }
    if (elements.invoiceNote) {
        elements.invoiceNote.value = '';
        elements.invoiceNote.disabled = true;
    }
    if (elements.invoiceDocumentType) {
        elements.invoiceDocumentType.value = '9006';
        elements.invoiceDocumentType.disabled = true;
    }
    if (elements.invoiceTaxId) {
        elements.invoiceTaxId.value = '';
        elements.invoiceTaxId.disabled = true;
    }
    if (elements.invoiceSerialNo) {
        elements.invoiceSerialNo.value = '';
        elements.invoiceSerialNo.disabled = true;
    }

    // Show modal
    resetFinalizePaymentButton();
    elements.paymentModal.style.display = 'block';

    // Update totals
    elements.modalTotalAmount.textContent = `${itemsTotal.toFixed(2)} TL`;
    updateRemainingAmount(itemsTotal);
}

function closePaymentModal() {
    elements.paymentModal.style.display = 'none';
    isSelectivePayment = false;
    if (!paymentInProgress) {
        resetFinalizePaymentButton();
    }
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

        const otherInputs = [elements.paymentNakit, elements.paymentKart, elements.paymentCari].filter(el => el !== input);
        let fullInput = null;
        let otherTotal = 0;

        otherInputs.forEach(el => {
            const v = parseFloat(el.value) || 0;
            otherTotal += v;
            if (Math.abs(v - total) < 0.01) {
                fullInput = el;
            }
        });

        // Move total if it resides entirely in one other input and no partial payments exist
        if (fullInput && Math.abs(otherTotal - total) < 0.01) {
            fullInput.value = '';
            input.value = total.toFixed(2);
            syncCardSplitRowsToTotal();
            updateRemainingAmount();
            input.select();
            return;
        }

        const remaining = Math.max(0, total - otherTotal);

        if (remaining > 0) {
            input.value = remaining.toFixed(2);
            syncCardSplitRowsToTotal();
            updateRemainingAmount();
            input.select();
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
    if (changedInput !== elements.paymentKart) {
        syncCardSplitRowsToTotal();
    }
    updateRemainingAmount();
}



function searchCustomers() {
    if (customerSearchTimer) {
        clearTimeout(customerSearchTimer);
    }
    customerSearchTimer = setTimeout(() => runCustomerSearch(), CUSTOMER_SEARCH_DEBOUNCE_MS);
}

async function getCustomerAccountsForSearch() {
    const now = Date.now();
    if (customerAccountsCache.expiresAt > now) {
        return customerAccountsCache.items;
    }
    const response = await fetch('/api/cari/hesaplar');
    const data = await response.json();
    if (!data.success) {
        return [];
    }
    customerAccountsCache = {
        expiresAt: now + CUSTOMER_ACCOUNTS_CACHE_MS,
        items: Array.isArray(data.hesaplar) ? data.hesaplar : []
    };
    return customerAccountsCache.items;
}

async function runCustomerSearch() {
    const query = elements.customerSearch.value.toLocaleLowerCase('tr-TR');
    if (query.length < 2) {
        elements.customerResults.style.display = 'none';
        return;
    }

    try {
        const accounts = await getCustomerAccountsForSearch();
        const latestQuery = elements.customerSearch.value.toLocaleLowerCase('tr-TR');
        if (latestQuery.length < 2) {
            elements.customerResults.style.display = 'none';
            return;
        }
        const results = accounts.filter(h =>
            String(h.cari_isim || '').toLocaleLowerCase('tr-TR').includes(latestQuery)
        );
        renderCustomerResults(results);
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
    if (paymentInProgress) {
        showNotification('ÖKC işlemi devam ediyor, lütfen tamamlanmasını bekleyin.', 'info');
        return;
    }
    if (!socket || !socket.connected) {
        showNotification('Sunucu bağlantısı yok. Bağlantı geldikten sonra tekrar deneyin.', 'error');
        return;
    }

    const nakit = centsToMoney(moneyToCents(elements.paymentNakit.value));
    const cardPayments = getCardPaymentParts();
    const kart = cardPayments.reduce((sum, amount) => sum + amount, 0);
    const cari = centsToMoney(moneyToCents(elements.paymentCari.value));

    const totalCents = moneyToCents(nakit) + moneyToCents(kart) + moneyToCents(cari);

    if (totalCents === 0) {
        showNotification('Ödeme tutarı girilmedi!', 'warning');
        return;
    }

    const paymentTotal = getCurrentPaymentTotal();
    const paymentTotalCents = moneyToCents(paymentTotal);

    if (Math.abs(totalCents - paymentTotalCents) > 1) {
        showNotification(
            `Girilen toplam (${centsToMoney(totalCents).toFixed(2)} TL), ödenecek tutarla (${centsToMoney(paymentTotalCents).toFixed(2)} TL) eşleşmeli.`,
            'warning'
        );
        return;
    }

    const payments = [];
    if (nakit > 0) payments.push({ type: 'Nakit', amount: nakit });
    cardPayments.forEach((amount, index) => {
        payments.push({
            type: 'Kredi Kartı',
            amount: centsToMoney(moneyToCents(amount)),
            description: cardPayments.length > 1 ? `Kredi Kartı ${index + 1}` : 'Kredi Kartı'
        });
    });
    if (cari > 0) {
        const customer = elements.selectedCustomer.value;
        if (!customer) {
            showNotification('Lütfen Cari hesap için bir müşteri seçiniz!', 'warning');
            return;
        }
        payments.push({ type: 'Açık Hesap', amount: cari, customer: customer });
    }

    const invoicePending = Boolean(elements.invoicePending && elements.invoicePending.checked);
    const invoiceTaxId = elements.invoiceTaxId ? elements.invoiceTaxId.value.replace(/\D/g, '') : '';
    const invoiceSerialNo = elements.invoiceSerialNo ? elements.invoiceSerialNo.value.trim() : '';
    const tokenBridgeTypes = ['token-bridge', 'beko-token', 'beko-yn-okc'];
    if (invoicePending && systemInfo.pos_enabled) {
        if (tokenBridgeTypes.includes(systemInfo.pos_type || '')) {
            if (![10, 11].includes(invoiceTaxId.length)) {
                showNotification('Fatura bilgi fişi için 10 haneli VKN veya 11 haneli TCKN giriniz.', 'warning');
                return;
            }
            if (!invoiceSerialNo) {
                showNotification('Fatura bilgi fişi için fatura/bilgi fişi seri no giriniz.', 'warning');
                return;
            }
        } else if (kart > 0) {
            showNotification('Bu POS/ÖKC tipi fatura bilgi fişi desteklemiyor; normal mali fiş basılmaması için işlem durduruldu.', 'error');
            return;
        }
    }

    const currentRole = getTerminalRole();
    const payload = {
        payments: payments,
        role: currentRole,
        invoice_pending: invoicePending,
        invoice_document_type: elements.invoiceDocumentType ? elements.invoiceDocumentType.value : '9006',
        invoice_tax_id: invoiceTaxId,
        invoice_serial_no: invoiceSerialNo,
        invoice_note: elements.invoiceNote ? elements.invoiceNote.value.trim() : ''
    };
    if (isSelectivePayment) {
        payload.item_quantities = getSelectedItemQuantities();
    }

    const posType = systemInfo.pos_type || '';
    const shouldWaitForPos = systemInfo.pos_enabled && (
        kart > 0 || tokenBridgeTypes.includes(posType)
    );

    if (shouldWaitForPos) {
        setFinalizePaymentWaiting();
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
    const currentRole = getTerminalRole();
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
    setupZReportLongPress();

    if (elements.btnTotalPayment) {
        elements.btnTotalPayment.onclick = () => {
            if (!currentMasa) {
                showNotification('Lütfen önce masa seçiniz!', 'warning');
                return;
            }
            if (currentItems.length === 0) {
                showNotification('Sipariş listesi boş!', 'warning');
                return;
            }
            if (currentTotal <= 0.01) {
                showNotification('Ödenecek tutar yok. Hesabı İkram Kapat ile kapatabilirsiniz.', 'info');
                return;
            }
            const isSelective = selectedItemKeys.length > 0;
            const defaultPaymentMethod = getDefaultPaymentMethod();
            console.log(`💶 btnTotalPayment clicked -> opening modal with ${defaultPaymentMethod} prefill (Selective: ${isSelective})`);
            openPaymentModal(defaultPaymentMethod, isSelective);
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

    if (elements.btnToggleOrderEntry) {
        elements.btnToggleOrderEntry.onclick = () => toggleCashierOrderEntry();
    }

    if (elements.btnSaveTableNote) {
        elements.btnSaveTableNote.onclick = () => saveCurrentTableNote();
    }

    if (elements.tableNoteInput) {
        elements.tableNoteInput.addEventListener('keydown', (event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
                event.preventDefault();
                saveCurrentTableNote();
            }
        });
    }

    if (elements.btnCari) {
        elements.btnCari.onclick = () => {
            window.location.href = '/cari';
        };
    }

    if (elements.btnReports) {
        elements.btnReports.onclick = () => {
            window.location.href = 'kasa_yonetimi.html';
        };
    }



    if (elements.btnAbout) {
        elements.btnAbout.onclick = () => {
            alert(`Restoran\nRestoran Yönetim Sistemi\n\nVersiyon: 1.0\nTerminal: ${systemInfo.terminal_id || '1'}`);
        };
    }

    // Modal & Payment Events


    if (elements.closePaymentModal) {
        elements.closePaymentModal.onclick = () => closePaymentModal();
    }

    if (elements.btnCancelPayment) {
        elements.btnCancelPayment.onclick = () => closePaymentModal();
    }

    if (elements.btnFinalizePayment) {
        elements.btnFinalizePayment.onclick = () => finalizeSplitPayment();
    }

    if (elements.btnAddCardSplit) {
        elements.btnAddCardSplit.onclick = () => addCardSplitRow();
    }

    if (elements.btnSplitCardsEqual) {
        elements.btnSplitCardsEqual.onclick = () => splitCardsEqual();
    }

    if (elements.invoicePending) {
        elements.invoicePending.onchange = () => {
            const enabled = elements.invoicePending.checked;
            [
                elements.invoiceDocumentType,
                elements.invoiceTaxId,
                elements.invoiceSerialNo,
                elements.invoiceNote
            ].forEach(el => {
                if (el) el.disabled = !enabled;
            });
            if (elements.invoicePending.checked) {
                if (elements.invoiceTaxId) elements.invoiceTaxId.focus();
            } else {
                if (elements.invoiceTaxId) elements.invoiceTaxId.value = '';
                if (elements.invoiceSerialNo) elements.invoiceSerialNo.value = '';
                if (elements.invoiceNote) elements.invoiceNote.value = '';
            }
        };
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
            syncCardSplitRowsToTotal();
            updateRemainingAmount();
        };
        elements.paymentKart.onfocus = () => handlePaymentInputFocus(elements.paymentKart);
    }

    // Transfer Modal Events
    if (elements.btnTransfer) {
        elements.btnTransfer.onclick = () => openTransferModal();
    }

    if (elements.btnOpenTablePicker) {
        elements.btnOpenTablePicker.onclick = () => openTablePickerModal();
    }

    if (elements.closeTablePickerModal) {
        elements.closeTablePickerModal.onclick = () => closeTablePickerModal();
    }

    if (elements.btnCancelTablePicker) {
        elements.btnCancelTablePicker.onclick = () => closeTablePickerModal();
    }

    if (elements.closeTransferModal) {
        elements.closeTransferModal.onclick = () => closeTransferModal();
    }

    if (elements.btnCancelTransfer) {
        elements.btnCancelTransfer.onclick = () => closeTransferModal();
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
        elements.btnPaySelected.onclick = () => openPaymentModal(getDefaultPaymentMethod(), true);
    }

    if (elements.btnCompSelected) {
        elements.btnCompSelected.onclick = () => setSelectedComplimentary(true);
    }

    if (elements.btnUncompSelected) {
        elements.btnUncompSelected.onclick = () => setSelectedComplimentary(false);
    }

    if (elements.btnCloseCompBill) {
        elements.btnCloseCompBill.onclick = () => closeComplimentaryBill();
    }

    if (elements.btnQuickWater) {
        elements.btnQuickWater.onclick = () => addQuickWaterToOrder();
    }

    if (elements.btnQuickDessert) {
        elements.btnQuickDessert.onclick = () => toggleQuickDessertForm();
    }

    if (elements.quickDessertProduct) {
        elements.quickDessertProduct.onchange = () => updateQuickDessertPreview();
    }

    if (elements.quickDessertGrams) {
        elements.quickDessertGrams.oninput = () => updateQuickDessertPreview();
        elements.quickDessertGrams.onkeydown = (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                addQuickDessertToOrder();
            }
        };
    }

    if (elements.btnQuickDessertAdd) {
        elements.btnQuickDessertAdd.onclick = () => addQuickDessertToOrder();
    }



    // Close modal on outside click
    window.onclick = (event) => {
        if (event.target == elements.paymentModal) {
            closePaymentModal();
        }
        if (event.target == elements.transferModal) {
            closeTransferModal();
        }
        if (event.target == elements.tablePickerModal) {
            closeTablePickerModal();
        }
    };

    // Courier Assignment
    if (elements.btnAssignCourier) {
        elements.btnAssignCourier.onclick = () => assignCourier();
    }
    if (elements.btnSendCourierInfo) {
        elements.btnSendCourierInfo.onclick = () => sendCourierInfo();
    }
}

/**
 * Courier Assignment logic
 */
function updateCourierArea() {
    if (!elements.courierAssignmentArea) return;

    if (currentMasa && isPaketMasa(currentMasa)) {
        elements.courierAssignmentArea.style.display = 'block';
        fetchCouriers();

        // Reset assigned info
        elements.assignedCourierInfo.style.display = 'none';
        elements.assignedCourierName.textContent = '';
    } else {
        elements.courierAssignmentArea.style.display = 'none';
    }
}

async function fetchCouriers() {
    if (!elements.courierSelect) return;

    try {
        const resp = await fetch('/api/couriers');
        const data = await resp.json();

        // Clear current options except first
        while (elements.courierSelect.options.length > 1) {
            elements.courierSelect.remove(1);
        }

        data.forEach(k => {
            if (!k.aktif) return;
            const opt = document.createElement('option');
            opt.value = k.id;
            opt.textContent = `${k.ad}${k.plaka ? ' (' + k.plaka + ')' : ''}`;
            opt.dataset.tel = k.telefon;
            elements.courierSelect.appendChild(opt);
        });
    } catch (err) {
        console.error('Error fetching couriers:', err);
    }
}

function assignCourier() {
    if (!currentMasa || !elements.courierSelect.value) {
        showNotification('Lütfen kurye seçiniz!', 'warning');
        return;
    }

    const sel = elements.courierSelect;
    const courierId = sel.value;
    const courierAd = sel.options[sel.selectedIndex].text;
    const courierTel = sel.options[sel.selectedIndex].dataset.tel;

    socket.emit('assign_courier', {
        masa: currentMasa,
        kurye_id: courierId,
        kurye_ad: courierAd,
        kurye_tel: courierTel
    });
}

function onCourierAssigned(data) {
    if (data.masa === currentMasa) {
        elements.assignedCourierInfo.style.display = 'block';
        elements.assignedCourierName.textContent = `Atanan: ${data.kurye_ad}`;
        elements.assignedCourierName.dataset.tel = data.kurye_tel || '';
        showNotification(`${data.masa} için ${data.kurye_ad} atandı.`, 'success');
    }
}

function sendCourierInfo() {
    const tel = elements.assignedCourierName.dataset.tel;
    if (!tel) {
        showNotification('Kurye telefon bilgisi bulunamadı!', 'error');
        return;
    }

    socket.emit('send_courier_info', {
        masa: currentMasa,
        kurye_tel: tel
    });
}

function onCourierMessageReady(data) {
    console.log('📱 WhatsApp message ready:', data);
    // WhatsApp'ı yeni pencerede aç
    window.open(data.whatsapp_url, '_blank');
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
/**
 * Initialize vertical resizer for order list
 */
function initResizer() {
    const resizer = elements.orderResizer;
    const container = document.querySelector('.order-list-container');

    if (!resizer || !container) return;

    let startY, startHeight;
    const MIN_ORDER_LIST_HEIGHT = 80;

    function getControlsReserveHeight() {
        return document.body.classList.contains('cashier-terminal') ? 240 : 180;
    }

    function getMaxOrderListHeight() {
        const panel = container.closest('.right-panel');
        if (!panel) return window.innerHeight * 0.7;

        const panelHeight = panel.getBoundingClientRect().height || window.innerHeight;
        let reservedHeight = getControlsReserveHeight();

        Array.from(panel.children).forEach(child => {
            if (child === container || child.classList.contains('controls-container')) return;

            const style = window.getComputedStyle(child);
            if (style.display === 'none' || style.position === 'absolute' || style.position === 'fixed') return;

            reservedHeight += child.getBoundingClientRect().height;
        });

        return Math.max(MIN_ORDER_LIST_HEIGHT, panelHeight - reservedHeight);
    }

    function applyOrderListHeight(rawHeight) {
        const maxHeight = getMaxOrderListHeight();
        const numericHeight = Number.parseFloat(rawHeight);
        if (!Number.isFinite(numericHeight)) return;

        const nextHeight = Math.max(MIN_ORDER_LIST_HEIGHT, Math.min(numericHeight, maxHeight));
        container.style.height = `${nextHeight}px`;
        container.style.flex = `0 0 ${nextHeight}px`;
    }

    function onMouseDown(e) {
        startY = e.clientY;
        startHeight = parseInt(document.defaultView.getComputedStyle(container).height, 10);

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);

        // Disable text selection and add active class
        document.body.style.userSelect = 'none';
        resizer.style.background = 'var(--accent-color)';
    }

    function onTouchStart(e) {
        const touch = e.touches[0];
        startY = touch.clientY;
        startHeight = parseInt(document.defaultView.getComputedStyle(container).height, 10);

        document.addEventListener('touchmove', onTouchMove, { passive: false });
        document.addEventListener('touchend', onTouchEnd);

        document.body.style.userSelect = 'none';
        resizer.style.background = 'var(--accent-color)';
    }

    function onMouseMove(e) {
        const newHeight = startHeight + (e.clientY - startY);
        applyOrderListHeight(newHeight);
    }

    function onTouchMove(e) {
        e.preventDefault();
        const touch = e.touches[0];
        const newHeight = startHeight + (touch.clientY - startY);
        applyOrderListHeight(newHeight);
    }

    function onMouseUp() {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);

        document.body.style.userSelect = '';
        resizer.style.background = '';

        // Save preference to localStorage
        localStorage.setItem('order_list_height', container.style.height);
    }

    function onTouchEnd() {
        document.removeEventListener('touchmove', onTouchMove);
        document.removeEventListener('touchend', onTouchEnd);

        document.body.style.userSelect = '';
        resizer.style.background = '';

        // Save preference to localStorage
        localStorage.setItem('order_list_height', container.style.height);
    }

    resizer.addEventListener('mousedown', onMouseDown);
    resizer.addEventListener('touchstart', onTouchStart, { passive: true });

    // Restore saved height
    const savedHeight = localStorage.getItem('order_list_height');
    if (savedHeight) {
        applyOrderListHeight(savedHeight);
    }

    window.addEventListener('resize', () => {
        if (container.style.height) {
            applyOrderListHeight(container.style.height);
        }
    });
}

/**
 * Initialize horizontal resizers for panels
 */
function initHorizontalResizers() {
    const resizerLeft = elements.resizerLeft;
    const resizerRight = elements.resizerRight;
    const leftPanel = elements.leftPanel;
    const rightPanel = elements.rightPanel;

    if (resizerLeft && leftPanel) {
        let startX, startWidth;

        function onMouseDown(e) {
            startX = e.clientX;
            startWidth = parseInt(document.defaultView.getComputedStyle(leftPanel).width, 10);

            document.addEventListener('mousemove', onMouseMoveLeft);
            document.addEventListener('mouseup', onMouseUpLeft);

            document.body.style.userSelect = 'none';
            resizerLeft.style.background = 'var(--accent-color)';
        }

        function onTouchStart(e) {
            const touch = e.touches[0];
            startX = touch.clientX;
            startWidth = parseInt(document.defaultView.getComputedStyle(leftPanel).width, 10);

            document.addEventListener('touchmove', onTouchMoveLeft, { passive: false });
            document.addEventListener('touchend', onTouchEndLeft);

            document.body.style.userSelect = 'none';
            resizerLeft.style.background = 'var(--accent-color)';
        }

        function onMouseMoveLeft(e) {
            const newWidth = startWidth + (e.clientX - startX);
            // Min 150px, Max 50vw
            if (newWidth > 150 && newWidth < (window.innerWidth * 0.5)) {
                leftPanel.style.flex = `0 0 ${newWidth}px`;
            }
        }

        function onTouchMoveLeft(e) {
            e.preventDefault();
            const touch = e.touches[0];
            const newWidth = startWidth + (touch.clientX - startX);
            // Min 150px, Max 50vw
            if (newWidth > 150 && newWidth < (window.innerWidth * 0.5)) {
                leftPanel.style.flex = `0 0 ${newWidth}px`;
            }
        }

        function onMouseUpLeft() {
            document.removeEventListener('mousemove', onMouseMoveLeft);
            document.removeEventListener('mouseup', onMouseUpLeft);
            document.body.style.userSelect = '';
            resizerLeft.style.background = '';
            localStorage.setItem('left_panel_width', leftPanel.style.flex);
        }

        function onTouchEndLeft() {
            document.removeEventListener('touchmove', onTouchMoveLeft);
            document.removeEventListener('touchend', onTouchEndLeft);
            document.body.style.userSelect = '';
            resizerLeft.style.background = '';
            localStorage.setItem('left_panel_width', leftPanel.style.flex);
        }

        resizerLeft.addEventListener('mousedown', onMouseDown);
        resizerLeft.addEventListener('touchstart', onTouchStart, { passive: true });

        // Restore saved width
        const savedLeftWidth = localStorage.getItem('left_panel_width');
        if (savedLeftWidth) {
            leftPanel.style.flex = savedLeftWidth;
        }
    }

    if (resizerRight && rightPanel) {
        let startX, startWidth;

        function onMouseDown(e) {
            startX = e.clientX;
            startWidth = parseInt(document.defaultView.getComputedStyle(rightPanel).width, 10);

            document.addEventListener('mousemove', onMouseMoveRight);
            document.addEventListener('mouseup', onMouseUpRight);

            document.body.style.userSelect = 'none';
            resizerRight.style.background = 'var(--accent-color)';
        }

        function onTouchStart(e) {
            const touch = e.touches[0];
            startX = touch.clientX;
            startWidth = parseInt(document.defaultView.getComputedStyle(rightPanel).width, 10);

            document.addEventListener('touchmove', onTouchMoveRight, { passive: false });
            document.addEventListener('touchend', onTouchEndRight);

            document.body.style.userSelect = 'none';
            resizerRight.style.background = 'var(--accent-color)';
        }

        function onMouseMoveRight(e) {
            // Right resizer moves left to expand right panel
            const newWidth = startWidth - (e.clientX - startX);
            // Min 300px, Max 60vw
            if (newWidth > 300 && newWidth < (window.innerWidth * 0.6)) {
                rightPanel.style.flex = `0 0 ${newWidth}px`;
            }
        }

        function onTouchMoveRight(e) {
            e.preventDefault();
            const touch = e.touches[0];
            const newWidth = startWidth - (touch.clientX - startX);
            // Min 300px, Max 60vw
            if (newWidth > 300 && newWidth < (window.innerWidth * 0.6)) {
                rightPanel.style.flex = `0 0 ${newWidth}px`;
            }
        }

        function onMouseUpRight() {
            document.removeEventListener('mousemove', onMouseMoveRight);
            document.removeEventListener('mouseup', onMouseUpRight);
            document.body.style.userSelect = '';
            resizerRight.style.background = '';
            localStorage.setItem('right_panel_width', rightPanel.style.flex);
        }

        function onTouchEndRight() {
            document.removeEventListener('touchmove', onTouchMoveRight);
            document.removeEventListener('touchend', onTouchEndRight);
            document.body.style.userSelect = '';
            resizerRight.style.background = '';
            localStorage.setItem('right_panel_width', rightPanel.style.flex);
        }

        resizerRight.addEventListener('mousedown', onMouseDown);
        resizerRight.addEventListener('touchstart', onTouchStart, { passive: true });

        // Restore saved width
        const savedRightWidth = localStorage.getItem('right_panel_width');
        if (savedRightWidth) {
            rightPanel.style.flex = savedRightWidth;
        }
    }
}
