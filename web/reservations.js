let systemInfo = {};
let menuData = {};
let prepPanels = [];
let reservationsPayload = { reservations: [], active_by_table: {}, active_count: 0, today_count: 0 };
let reservationFilter = 'active';
let reservationSearchTerm = '';
let reservationMenuItems = [];
let socket = null;

const elements = {};
const elementIds = [
    'pageSubtitle',
    'summaryToday',
    'summaryUpcoming',
    'summaryTotal',
    'summaryCancelled',
    'reservationFilters',
    'reservationSearch',
    'reservationTableBody',
    'btnNewReservation',
    'reservationModal',
    'reservationModalTitle',
    'btnCloseModal',
    'btnDismissModal',
    'reservationForm',
    'reservationId',
    'reservationCustomer',
    'reservationPhone',
    'reservationSource',
    'reservationDate',
    'reservationTime',
    'reservationTable',
    'reservationGuests',
    'reservationStatus',
    'reservationMenuCategory',
    'reservationMenuProduct',
    'reservationMenuQty',
    'reservationMenuNote',
    'btnAddReservationMenuItem',
    'reservationMenuItems',
    'reservationMenu',
    'reservationNote',
    'btnCancelReservation',
    'btnSaveReservation',
    'toast'
];

document.addEventListener('DOMContentLoaded', initReservationsPage);

async function initReservationsPage() {
    elementIds.forEach(id => {
        elements[id] = document.getElementById(id);
    });

    setupEventListeners();
    await loadInitialData();
    connectSocket();
}

function setupEventListeners() {
    elements.btnNewReservation.onclick = () => openReservationModal();
    elements.btnCloseModal.onclick = closeReservationModal;
    elements.btnDismissModal.onclick = closeReservationModal;
    elements.reservationForm.onsubmit = saveReservation;
    elements.btnCancelReservation.onclick = () => {
        const reservationId = elements.reservationId.value;
        if (reservationId) updateReservationStatus(reservationId, 'iptal');
    };

    elements.reservationFilters.onclick = event => {
        const button = event.target.closest('button[data-filter]');
        if (!button) return;
        reservationFilter = button.dataset.filter || 'active';
        renderReservations();
    };

    elements.reservationSearch.oninput = () => {
        reservationSearchTerm = elements.reservationSearch.value || '';
        renderReservations();
    };

    elements.reservationMenuCategory.onchange = () => {
        populateReservationProductOptions();
    };
    elements.btnAddReservationMenuItem.onclick = addReservationMenuItemFromForm;
    elements.reservationMenuItems.onclick = event => {
        const button = event.target.closest('button[data-menu-remove]');
        if (!button) return;
        const index = Number(button.dataset.menuRemove);
        if (!Number.isNaN(index)) {
            reservationMenuItems.splice(index, 1);
            renderReservationMenuItems();
        }
    };

    elements.reservationTableBody.onclick = event => {
        const button = event.target.closest('button[data-action][data-id]');
        if (!button) return;
        const reservationId = button.dataset.id;
        const action = button.dataset.action;
        if (action === 'edit') {
            openReservationModal(getReservationById(reservationId));
        } else if (action === 'arrived') {
            updateReservationStatus(reservationId, 'geldi');
        } else if (action === 'cancel') {
            updateReservationStatus(reservationId, 'iptal');
        }
    };

    elements.reservationModal.onclick = event => {
        if (event.target === elements.reservationModal) closeReservationModal();
    };
}

async function loadInitialData() {
    try {
        const [systemResponse, reservationsResponse, menuResponse, prepResponse] = await Promise.all([
            fetch('/api/system/info', { cache: 'no-store' }),
            fetch('/api/reservations', { cache: 'no-store' }),
            fetch('/api/order-menu', { cache: 'no-store' }),
            fetch('/api/prep-panels', { cache: 'no-store' })
        ]);
        if (!systemResponse.ok) throw new Error('Sistem bilgisi alınamadı');
        if (!reservationsResponse.ok) throw new Error('Rezervasyonlar alınamadı');
        if (!menuResponse.ok) throw new Error('Menü alınamadı');

        systemInfo = await systemResponse.json();
        reservationsPayload = normalizeReservationsPayload(await reservationsResponse.json());
        menuData = await menuResponse.json();
        const prepData = prepResponse.ok ? await prepResponse.json() : {};
        prepPanels = Array.isArray(prepData.panels) ? prepData.panels : [];
        populateReservationTableOptions();
        populateReservationMenuCategories();
        renderReservations();
    } catch (error) {
        showToast(error.message || 'Rezervasyon sayfası yüklenemedi', 'error');
        elements.reservationTableBody.innerHTML = '<tr><td colspan="8" class="empty">Rezervasyonlar yüklenemedi</td></tr>';
    }
}

function connectSocket() {
    if (typeof io !== 'function') return;
    socket = io({
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000
    });
    socket.on('reservations_update', data => {
        reservationsPayload = normalizeReservationsPayload(data);
        renderReservations();
    });
    socket.on('system_info', data => {
        systemInfo = data || systemInfo;
        populateReservationTableOptions(elements.reservationTable.value);
    });
    socket.on('system_update', data => {
        systemInfo = { ...systemInfo, ...(data || {}) };
        populateReservationTableOptions(elements.reservationTable.value);
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

function getReservationById(id) {
    return (reservationsPayload.reservations || []).find(item => item.id === id) || null;
}

function isReservationUpcoming(reservation) {
    if (!reservation || reservation.status !== 'planlandi') return false;
    return String(reservation.date || '') >= String(reservationsPayload.today || getLocalDateValue());
}

function isReservationToday(reservation) {
    return String(reservation?.date || '') === String(reservationsPayload.today || getLocalDateValue());
}

function isReservationPast(reservation) {
    if (!reservation || reservation.status === 'iptal') return false;
    return String(reservation.date || '') < String(reservationsPayload.today || getLocalDateValue());
}

function normalizeSearchText(value) {
    return String(value || '')
        .trim()
        .toLocaleLowerCase('tr-TR')
        .replace(/ı/g, 'i')
        .replace(/ğ/g, 'g')
        .replace(/ü/g, 'u')
        .replace(/ş/g, 's')
        .replace(/ö/g, 'o')
        .replace(/ç/g, 'c');
}

function getReservationSearchHaystack(reservation) {
    return normalizeSearchText([
        reservation.customer_name,
        reservation.phone,
        reservation.masa,
        reservation.menu_preferences,
        formatReservationMenuItems(reservation.menu_items),
        reservation.note,
        reservation.date,
        reservation.time,
        reservation.day,
        reservation.source_label,
        reservation.status_label
    ].filter(Boolean).join(' '));
}

function matchesReservationFilter(reservation) {
    if (!reservation) return false;
    if (reservationFilter === 'all') return true;
    if (reservationFilter === 'today') return isReservationToday(reservation);
    if (reservationFilter === 'past') return isReservationPast(reservation);
    if (reservationFilter === 'cancelled') return reservation.status === 'iptal';
    return isReservationUpcoming(reservation);
}

function getFilteredReservations() {
    const search = normalizeSearchText(reservationSearchTerm);
    return (reservationsPayload.reservations || [])
        .filter(matchesReservationFilter)
        .filter(reservation => !search || getReservationSearchHaystack(reservation).includes(search))
        .sort(compareReservations);
}

function compareReservations(a, b) {
    const aKey = `${a?.date || '9999-12-31'} ${a?.time || '23:59'} ${a?.customer_name || ''}`;
    const bKey = `${b?.date || '9999-12-31'} ${b?.time || '23:59'} ${b?.customer_name || ''}`;
    return aKey.localeCompare(bKey, 'tr');
}

function renderReservations() {
    const reservations = getFilteredReservations();
    const allReservations = reservationsPayload.reservations || [];
    const cancelledCount = allReservations.filter(item => item.status === 'iptal').length;

    elements.summaryToday.textContent = reservationsPayload.today_count || 0;
    elements.summaryUpcoming.textContent = reservationsPayload.active_count || 0;
    elements.summaryTotal.textContent = allReservations.length;
    elements.summaryCancelled.textContent = cancelledCount;
    elements.pageSubtitle.textContent = `${reservations.length} kayıt listeleniyor`;
    updateFilterButtons();

    if (!reservations.length) {
        const emptyText = reservationSearchTerm
            ? 'Aramaya uygun rezervasyon yok'
            : 'Bu filtrede rezervasyon yok';
        elements.reservationTableBody.innerHTML = `<tr><td colspan="8" class="empty">${emptyText}</td></tr>`;
        return;
    }

    elements.reservationTableBody.innerHTML = reservations.map(renderReservationRow).join('');
}

function updateFilterButtons() {
    elements.reservationFilters.querySelectorAll('button[data-filter]').forEach(button => {
        const isActive = button.dataset.filter === reservationFilter;
        button.classList.toggle('active', isActive);
        button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
}

function renderReservationRow(reservation) {
    const id = escapeHtml(reservation.id);
    const quickActions = reservation.status === 'planlandi'
        ? `
            <button class="btn" type="button" data-action="arrived" data-id="${id}">Geldi</button>
            <button class="btn btn-danger" type="button" data-action="cancel" data-id="${id}">İptal</button>
        `
        : '';
    const structuredMenu = formatReservationMenuItems(reservation.menu_items);
    const menuNote = [
        structuredMenu ? `Menü: ${structuredMenu}` : (reservation.menu_preferences ? `Menü: ${reservation.menu_preferences}` : ''),
        reservation.note ? `Not: ${reservation.note}` : ''
    ].filter(Boolean).join('\n');
    return `
        <tr>
            <td>${escapeHtml(formatShortDate(reservation.date))}<div class="muted">${escapeHtml(reservation.day || '')}</div></td>
            <td><strong>${escapeHtml(reservation.time || '')}</strong></td>
            <td>${escapeHtml(reservation.masa || '')}</td>
            <td>${Number(reservation.guest_count || 0)}</td>
            <td class="customer-cell">
                <strong>${escapeHtml(reservation.customer_name || '')}</strong>
                <span>${escapeHtml(reservation.phone || '')}</span>
            </td>
            <td><div class="line-clamp">${escapeHtml(menuNote || '-')}</div></td>
            <td>${renderStatusBadge(reservation)}</td>
            <td>
                <div class="actions">
                    <button class="btn" type="button" data-action="edit" data-id="${id}">Düzenle</button>
                    ${quickActions}
                </div>
            </td>
        </tr>
    `;
}

function renderStatusBadge(reservation) {
    const status = reservation.status || 'planlandi';
    const label = reservation.status_label || 'Planlandı';
    return `<span class="status-badge status-${escapeHtml(status)}">${escapeHtml(label)}</span>`;
}

function getReservationTableNames() {
    const salons = Array.isArray(systemInfo.salons) ? systemInfo.salons : [];
    if (salons.length > 0) {
        return salons
            .flatMap(salon => Array.isArray(salon.tables) ? salon.tables : [])
            .map(table => String(table || '').trim())
            .filter(Boolean);
    }

    const masaCount = Number(systemInfo.masa_sayisi || 0);
    if (masaCount > 0) {
        return Array.from({ length: masaCount }, (_, index) => `Masa ${index + 1}`);
    }

    return [];
}

function populateReservationTableOptions(selectedTable = '') {
    const tables = getReservationTableNames();
    elements.reservationTable.innerHTML = '';

    if (!tables.length) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'Masa yok';
        elements.reservationTable.appendChild(option);
        return;
    }

    tables.forEach(table => {
        const option = document.createElement('option');
        option.value = table;
        option.textContent = table;
        elements.reservationTable.appendChild(option);
    });

    if (selectedTable && tables.includes(selectedTable)) {
        elements.reservationTable.value = selectedTable;
    }
}

function getMenuCategories() {
    return Object.keys(menuData || {}).filter(category => Array.isArray(menuData[category]) && menuData[category].length);
}

function getMenuItemsForCategory(category) {
    return Array.isArray(menuData?.[category]) ? menuData[category] : [];
}

function getPrepPanelName(panelId) {
    const panel = (prepPanels || []).find(item => item.id === panelId);
    return panel?.name || panelId || 'Reyon';
}

function populateReservationMenuCategories(selectedCategory = '') {
    const categories = getMenuCategories();
    elements.reservationMenuCategory.innerHTML = '';
    if (!categories.length) {
        elements.reservationMenuCategory.innerHTML = '<option value="">Menü yok</option>';
        populateReservationProductOptions();
        return;
    }
    categories.forEach(category => {
        const option = document.createElement('option');
        option.value = category;
        option.textContent = category;
        elements.reservationMenuCategory.appendChild(option);
    });
    if (selectedCategory && categories.includes(selectedCategory)) {
        elements.reservationMenuCategory.value = selectedCategory;
    }
    populateReservationProductOptions();
}

function populateReservationProductOptions() {
    const category = elements.reservationMenuCategory.value;
    const items = getMenuItemsForCategory(category);
    elements.reservationMenuProduct.innerHTML = '';
    if (!items.length) {
        elements.reservationMenuProduct.innerHTML = '<option value="">Ürün yok</option>';
        return;
    }
    items.forEach(item => {
        const name = String(item?.[0] || '').trim();
        if (!name) return;
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        elements.reservationMenuProduct.appendChild(option);
    });
}

function getPanelForMenuItem(productName, category) {
    const productText = normalizeSearchText(productName);
    for (const panel of prepPanels || []) {
        const keywords = [...(panel.product_keywords || []), ...(panel.category_keywords || [])];
        if (keywords.some(keyword => productText.includes(normalizeSearchText(keyword)))) {
            return panel.id;
        }
    }
    return '';
}

function addReservationMenuItemFromForm() {
    const category = elements.reservationMenuCategory.value;
    const product = elements.reservationMenuProduct.value;
    const qty = Number(elements.reservationMenuQty.value || 1);
    if (!category || !product) {
        showToast('Menü ürünü seçin', 'error');
        return;
    }
    if (!Number.isFinite(qty) || qty <= 0 || qty > 999) {
        showToast('Geçerli adet girin', 'error');
        return;
    }
    const panel = getPanelForMenuItem(product, category);
    reservationMenuItems.push({
        urun: product,
        kategori: category,
        adet: qty,
        not: elements.reservationMenuNote.value.trim(),
        panel,
        panel_adi: getPrepPanelName(panel)
    });
    elements.reservationMenuQty.value = '1';
    elements.reservationMenuNote.value = '';
    renderReservationMenuItems();
}

function formatReservationMenuItem(item) {
    if (!item) return '';
    const qty = Number(item.adet || 1);
    const qtyText = Number.isInteger(qty) ? String(qty) : String(qty).replace('.', ',');
    const note = item.not ? ` (${item.not})` : '';
    return `${qtyText}x ${item.urun || ''}${note}`;
}

function formatReservationMenuItems(items) {
    if (!Array.isArray(items) || !items.length) return '';
    return items.map(formatReservationMenuItem).filter(Boolean).join('\n');
}

function syncReservationMenuSummary() {
    const summary = formatReservationMenuItems(reservationMenuItems);
    if (summary) {
        elements.reservationMenu.value = summary;
    }
}

function renderReservationMenuItems() {
    if (!reservationMenuItems.length) {
        elements.reservationMenuItems.innerHTML = '<div class="menu-empty">Menü ürünü eklenmedi</div>';
        elements.reservationMenu.value = '';
        return;
    }
    elements.reservationMenuItems.innerHTML = reservationMenuItems.map((item, index) => `
        <div class="reservation-menu-chip">
            <div>
                <strong>${escapeHtml(formatReservationMenuItem(item))}</strong>
                <span>${escapeHtml(item.kategori || '')}${item.panel_adi ? ` · ${escapeHtml(item.panel_adi)}` : ''}</span>
            </div>
            <button class="btn btn-danger" type="button" data-menu-remove="${index}">Sil</button>
        </div>
    `).join('');
    syncReservationMenuSummary();
}

function openReservationModal(reservation = null) {
    populateReservationTableOptions(reservation?.masa || '');
    elements.reservationModalTitle.textContent = reservation ? 'Rezervasyon Düzenle' : 'Yeni Rezervasyon';
    elements.reservationId.value = reservation?.id || '';
    elements.reservationCustomer.value = reservation?.customer_name || '';
    elements.reservationPhone.value = reservation?.phone || '';
    elements.reservationSource.value = reservation?.source || 'telefon';
    elements.reservationDate.value = reservation?.date || getLocalDateValue();
    elements.reservationTime.value = reservation?.time || getDefaultReservationTime();
    elements.reservationGuests.value = reservation?.guest_count || 2;
    elements.reservationStatus.value = reservation?.status || 'planlandi';
    reservationMenuItems = Array.isArray(reservation?.menu_items)
        ? reservation.menu_items.map(item => ({ ...item }))
        : [];
    renderReservationMenuItems();
    elements.reservationMenu.value = reservation?.menu_preferences || '';
    elements.reservationNote.value = reservation?.note || '';
    elements.btnCancelReservation.style.display = reservation?.id ? '' : 'none';
    elements.reservationModal.classList.add('open');
    elements.reservationCustomer.focus();
}

function closeReservationModal() {
    elements.reservationModal.classList.remove('open');
}

function getReservationFormPayload() {
    return {
        customer_name: elements.reservationCustomer.value,
        phone: elements.reservationPhone.value,
        source: elements.reservationSource.value,
        date: elements.reservationDate.value,
        time: elements.reservationTime.value,
        masa: elements.reservationTable.value,
        guest_count: Number(elements.reservationGuests.value || 0),
        status: elements.reservationStatus.value,
        menu_items: reservationMenuItems.map(item => ({
            urun: item.urun,
            kategori: item.kategori,
            adet: item.adet,
            not: item.not || ''
        })),
        menu_preferences: elements.reservationMenu.value,
        note: elements.reservationNote.value
    };
}

async function saveReservation(event) {
    event.preventDefault();
    const reservationId = elements.reservationId.value;
    const url = reservationId
        ? `/api/reservations/${encodeURIComponent(reservationId)}`
        : '/api/reservations';
    const method = reservationId ? 'PUT' : 'POST';

    try {
        elements.btnSaveReservation.disabled = true;
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(getReservationFormPayload())
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Rezervasyon kaydedilemedi');
        }
        reservationsPayload = normalizeReservationsPayload(data.reservations);
        closeReservationModal();
        renderReservations();
        showToast('Rezervasyon kaydedildi', 'success');
    } catch (error) {
        showToast(error.message || 'Rezervasyon kaydedilemedi', 'error');
    } finally {
        elements.btnSaveReservation.disabled = false;
    }
}

async function updateReservationStatus(reservationId, status) {
    try {
        const response = await fetch(`/api/reservations/${encodeURIComponent(reservationId)}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Rezervasyon güncellenemedi');
        }
        reservationsPayload = normalizeReservationsPayload(data.reservations);
        closeReservationModal();
        renderReservations();
        showToast(status === 'geldi' ? 'Rezervasyon geldi olarak işaretlendi' : 'Rezervasyon iptal edildi', 'success');
    } catch (error) {
        showToast(error.message || 'Rezervasyon güncellenemedi', 'error');
    }
}

function getLocalDateValue(date = new Date()) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function getDefaultReservationTime() {
    const date = new Date();
    date.setMinutes(Math.ceil((date.getMinutes() + 1) / 30) * 30, 0, 0);
    if (date.getHours() >= 23 && date.getMinutes() > 30) {
        return '19:00';
    }
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function formatShortDate(value) {
    const parts = String(value || '').split('-');
    if (parts.length !== 3) return value || '';
    return `${parts[2]}.${parts[1]}.${parts[0]}`;
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));
}

function showToast(message, type = 'info') {
    elements.toast.textContent = message;
    elements.toast.className = `toast show ${type}`;
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => {
        elements.toast.className = 'toast';
    }, 3500);
}
