(function () {
    const ALL_CATEGORY = "__all__";
    const apiMenuUrl = "/api/public/menu";
    const snapshotUrl = "/data/tokatliva_menu.json";

    const state = {
        data: null,
        activeCategory: ALL_CATEGORY,
        query: "",
        sort: "source"
    };

    const el = {
        categorySummary: document.getElementById("categorySummary"),
        itemSummary: document.getElementById("itemSummary"),
        sourceLabel: document.getElementById("sourceLabel"),
        activeTitle: document.getElementById("activeTitle"),
        activeCount: document.getElementById("activeCount"),
        categoryTabs: document.getElementById("categoryTabs"),
        menuGrid: document.getElementById("menuGrid"),
        searchInput: document.getElementById("searchInput"),
        sortSelect: document.getElementById("sortSelect")
    };

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function normalize(value) {
        return String(value || "").toLocaleLowerCase("tr-TR").trim();
    }

    function formatSourceLabel(data) {
        const sourceName = data.source_name || "tokatliva.com";
        if (!data.fetched_at) return sourceName;
        const date = new Date(data.fetched_at);
        if (Number.isNaN(date.getTime())) return sourceName;
        return `${sourceName} | ${date.toLocaleDateString("tr-TR")}`;
    }

    function formatPriceText(price) {
        return `${Number(price || 0).toLocaleString("tr-TR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        })}TL`;
    }

    function normalizeApiItem(item) {
        if (Array.isArray(item)) {
            const price = Number(item[1] || 0);
            return {
                name: String(item[0] || ""),
                price,
                price_text: formatPriceText(price),
                image_url: String(item[6] || ""),
                menu_visible: item.length <= 7 || isMenuVisible(item[7])
            };
        }

        const price = Number(item.price ?? item.fiyat ?? 0);
        return {
            name: String(item.name || item.urun || item.urun_adi || ""),
            price,
            price_text: item.price_text || formatPriceText(price),
            image_url: String(item.image_url || ""),
            menu_visible: item.menu_visible !== false
        };
    }

    function isMenuVisible(value) {
        if (typeof value === "boolean") return value;
        return !["0", "false", "hayir", "hayır", "no", "off"].includes(String(value).trim().toLocaleLowerCase("tr-TR"));
    }

    function normalizeMenuPayload(payload) {
        if (!payload || !payload.menu) return payload;

        const categories = Object.entries(payload.menu).map(([name, items]) => ({
            name,
            items: (items || []).map(normalizeApiItem).filter((item) => item.name && item.menu_visible)
        })).filter((category) => category.items.length);

        return {
            source: apiMenuUrl,
            source_name: "Satış otomasyonu",
            fetched_at: new Date().toISOString(),
            categories
        };
    }

    function allItems() {
        if (!state.data) return [];
        return state.data.categories.flatMap((category, categoryIndex) => {
            return category.items.map((item, itemIndex) => ({
                ...item,
                category: category.name,
                sourceIndex: categoryIndex * 1000 + itemIndex
            }));
        });
    }

    function visibleItems() {
        let items = allItems();
        if (!state.query && state.activeCategory !== ALL_CATEGORY) {
            items = items.filter((item) => item.category === state.activeCategory);
        }
        if (state.query) {
            const query = normalize(state.query);
            items = items.filter((item) => {
                return normalize(item.name).includes(query) || normalize(item.category).includes(query);
            });
        }
        if (state.sort === "price_asc") {
            items.sort((a, b) => Number(a.price || 0) - Number(b.price || 0));
        } else if (state.sort === "price_desc") {
            items.sort((a, b) => Number(b.price || 0) - Number(a.price || 0));
        } else if (state.sort === "name_asc") {
            items.sort((a, b) => String(a.name).localeCompare(String(b.name), "tr"));
        } else {
            items.sort((a, b) => a.sourceIndex - b.sourceIndex);
        }
        return items;
    }

    function categoryCount(categoryName) {
        if (categoryName === ALL_CATEGORY) return allItems().length;
        const category = state.data.categories.find((entry) => entry.name === categoryName);
        return category ? category.items.length : 0;
    }

    function getInitials(name) {
        const parts = String(name || "L").trim().split(/\s+/).filter(Boolean);
        return parts.slice(0, 2).map((part) => part[0]).join("").toLocaleUpperCase("tr-TR") || "L";
    }

    function renderPrice(item) {
        const raw = String(item.price_text || "").replace(/\s*TL$/i, "");
        const price = raw || Number(item.price || 0).toLocaleString("tr-TR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
        return `${escapeHtml(price)}<span>TL</span>`;
    }

    function renderTabs() {
        const categories = [{ name: ALL_CATEGORY, label: "Tümü" }].concat(
            state.data.categories.map((category) => ({ name: category.name, label: category.name }))
        );
        el.categoryTabs.innerHTML = categories.map((category) => {
            const active = category.name === state.activeCategory ? " active" : "";
            return `
                <button class="tab${active}" type="button" data-category="${escapeHtml(category.name)}">
                    ${escapeHtml(category.label)} (${categoryCount(category.name)})
                </button>`;
        }).join("");
    }

    function renderProducts() {
        const items = visibleItems();
        const activeLabel = state.activeCategory === ALL_CATEGORY ? "Tüm Menü" : state.activeCategory;
        el.activeTitle.textContent = state.query ? "Arama" : activeLabel;
        el.activeCount.textContent = `${items.length} ürün`;

        if (!items.length) {
            el.menuGrid.innerHTML = '<div class="empty">Ürün bulunamadı.</div>';
            return;
        }

        el.menuGrid.innerHTML = items.map((item) => {
            const image = item.image_url
                ? `<img src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.name)}" loading="lazy">`
                : "";
            return `
                <article class="product">
                    <div class="product-image">
                        ${image}
                        <div class="product-fallback" ${image ? "hidden" : ""}>${escapeHtml(getInitials(item.name))}</div>
                    </div>
                    <div class="product-body">
                        <h3 class="product-name">${escapeHtml(item.name)}</h3>
                        <div class="product-meta">${escapeHtml(item.category)}</div>
                        <div class="product-price">${renderPrice(item)}</div>
                    </div>
                </article>`;
        }).join("");

        el.menuGrid.querySelectorAll(".product-image img").forEach((image) => {
            image.addEventListener("error", () => {
                image.hidden = true;
                const fallback = image.nextElementSibling;
                if (fallback) fallback.hidden = false;
            });
        });
    }

    function renderShell() {
        const itemCount = allItems().length;
        el.categorySummary.textContent = `${state.data.categories.length} kategori`;
        el.itemSummary.textContent = `${itemCount} ürün`;
        el.sourceLabel.textContent = formatSourceLabel(state.data);
        renderTabs();
        renderProducts();
    }

    async function fetchJson(url) {
        const response = await fetch(url, { cache: "no-store" });
        if (!response.ok) throw new Error("Menü verisi alınamadı");
        return response.json();
    }

    async function loadMenu() {
        try {
            state.data = normalizeMenuPayload(await fetchJson(apiMenuUrl));
        } catch (error) {
            state.data = normalizeMenuPayload(await fetchJson(snapshotUrl));
        }
        renderShell();
    }

    el.categoryTabs.addEventListener("click", (event) => {
        const button = event.target.closest("[data-category]");
        if (!button) return;
        state.activeCategory = button.dataset.category || ALL_CATEGORY;
        renderTabs();
        renderProducts();
    });

    el.searchInput.addEventListener("input", (event) => {
        state.query = event.target.value || "";
        renderProducts();
    });

    el.sortSelect.addEventListener("change", (event) => {
        state.sort = event.target.value || "source";
        renderProducts();
    });

    loadMenu().catch(() => {
        el.menuGrid.innerHTML = '<div class="empty">Menü yüklenemedi.</div>';
    });
}());
